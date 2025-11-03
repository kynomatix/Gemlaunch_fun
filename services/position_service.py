"""
Position tracking service with FTX-style average-cost rebasing

This service calculates weighted average entry prices and tracks position size
across multiple buys and sells, supporting linked-wallet aggregation.
"""

import logging
from decimal import Decimal
from datetime import datetime, timezone
from models import db, Position, TradeEvent, User, Token, LinkedWallet

class PositionService:
    """Service for computing and caching user position metrics"""
    
    @staticmethod
    def compute_position(user, token):
        """
        Compute position metrics for a user+token using average-cost method
        
        Algorithm:
        - For BUY: cost_basis += qty * price_kas; position_qty += qty; avg_entry = cost_basis / position_qty
        - For SELL: cost_basis -= avg_entry * sell_qty; position_qty -= sell_qty
        - When position_qty hits zero, reset cost_basis and avg_entry to zero
        
        Args:
            user: User object or user_id
            token: Token object or token_id
            
        Returns:
            dict with position metrics:
            {
                'qty_remaining': Decimal,
                'cost_basis_kas': Decimal,
                'avg_entry_price_kas': Decimal,
                'avg_entry_mc_kas': Decimal,  # avg_entry * circulating_supply
                'realized_pnl_kas': Decimal,
                'last_trade_event_id': int or None
            }
        """
        # Normalize inputs to IDs
        user_id = user.id if hasattr(user, 'id') else user
        token_id = token.id if hasattr(token, 'id') else token
        
        # Get User and Token objects if needed
        if not hasattr(user, 'id'):
            user = User.query.get(user_id)
        if not hasattr(token, 'id'):
            token = Token.query.get(token_id)
        
        if not user or not token:
            logging.error(f"Invalid user_id={user_id} or token_id={token_id}")
            return None
        
        # Get all wallet addresses for this user (primary + linked)
        wallet_addresses = PositionService._get_user_wallets(user)
        
        if not wallet_addresses:
            logging.warning(f"No wallet addresses found for user {user_id}")
            return {
                'qty_remaining': Decimal('0'),
                'cost_basis_kas': Decimal('0'),
                'avg_entry_price_kas': Decimal('0'),
                'avg_entry_mc_kas': Decimal('0'),
                'realized_pnl_kas': Decimal('0'),
                'last_trade_event_id': None
            }
        
        # Get all trade events for user's wallets on this token (time-ordered)
        trade_events = TradeEvent.query.filter(
            TradeEvent.token_id == token_id,
            TradeEvent.user_wallet_address.in_(wallet_addresses)
        ).order_by(TradeEvent.timestamp.asc(), TradeEvent.id.asc()).all()
        
        if not trade_events:
            logging.debug(f"No trades found for user {user_id} on token {token_id}")
            return {
                'qty_remaining': Decimal('0'),
                'cost_basis_kas': Decimal('0'),
                'avg_entry_price_kas': Decimal('0'),
                'avg_entry_mc_kas': Decimal('0'),
                'realized_pnl_kas': Decimal('0'),
                'last_trade_event_id': None
            }
        
        # Apply average-cost algorithm
        position_qty = Decimal('0')
        cost_basis = Decimal('0')
        avg_entry = Decimal('0')
        realized_pnl = Decimal('0')
        last_event_id = None
        
        for event in trade_events:
            kas_amount = Decimal(str(event.kas_amount))
            token_amount_wei = Decimal(str(event.token_amount))
            
            # Skip events with zero or negative token amounts (invalid/stale events)
            if token_amount_wei <= 0:
                logging.warning(f"Skipping TradeEvent {event.id} with invalid token_amount: {token_amount_wei}")
                continue
            
            # Convert token amount from WEI to human-readable (divide by 10^18)
            token_amount = token_amount_wei / Decimal('1000000000000000000')
            
            # Price per token for this trade (in KAS)
            price_kas = kas_amount / token_amount if token_amount > 0 else Decimal('0')
            
            if event.trade_type in ('buy', 'dex_buy'):
                # BUY (bonding curve or DEX): Add to position with weighted average
                cost_basis += kas_amount  # Total KAS spent
                position_qty += token_amount
                
                # Recalculate weighted average entry price
                if position_qty > 0:
                    avg_entry = cost_basis / position_qty
                
                trade_label = "DEX_BUY" if event.trade_type == 'dex_buy' else "BUY"
                logging.debug(f"{trade_label}: +{token_amount} @ {price_kas:.12f} KAS | Position: {position_qty}, Avg Entry: {avg_entry:.12f}")
            
            elif event.trade_type == 'airdrop':
                # AIRDROP: Add to position with $0 cost basis (reduces average entry price)
                # This shows the value of community engagement - free tokens lower your avg cost
                position_qty += token_amount
                # Do NOT add to cost_basis (kas_amount is already 0 for airdrops)
                
                # Recalculate weighted average entry price (will decrease due to $0 cost tokens)
                if position_qty > 0 and cost_basis > 0:
                    avg_entry = cost_basis / position_qty
                elif position_qty > 0 and cost_basis == 0:
                    # All tokens from airdrops - $0 average
                    avg_entry = Decimal('0')
                
                logging.debug(f"AIRDROP: +{token_amount} @ $0 | Position: {position_qty}, Avg Entry: {avg_entry:.12f} (reduced by airdrop)")
            
            elif event.trade_type in ('sell', 'dex_sell'):
                # SELL (bonding curve or DEX): Reduce position with REBASING cost basis (FTX-style de-risking)
                sell_qty = min(token_amount, position_qty)  # Can't sell more than we have
                
                if position_qty > 0:
                    # Realized P&L calculation
                    if avg_entry > 0:
                        # Normal case: (sell_price - avg_entry) * qty_sold
                        pnl_this_sale = (price_kas - avg_entry) * sell_qty
                    else:
                        # Airdrop-only case (avg_entry = 0): entire sale proceeds are profit
                        pnl_this_sale = price_kas * sell_qty
                    
                    realized_pnl += pnl_this_sale
                    
                    # REBASING: Subtract actual sale proceeds from cost basis
                    # This "de-risks" your position by reflecting profits taken
                    cost_basis -= kas_amount  # Use actual proceeds, not original cost
                    
                    # Handle negative cost basis edge case (can happen when selling airdrops)
                    # Negative cost basis means you've taken out more than you put in (pure profit)
                    if cost_basis < 0:
                        cost_basis = Decimal('0')
                    
                    position_qty -= sell_qty
                    
                    # Recalculate avg entry based on reduced cost basis
                    if position_qty > 0 and cost_basis > 0:
                        avg_entry = cost_basis / position_qty
                    elif position_qty > 0:
                        # Position remains but cost_basis is 0 (all remaining tokens are from airdrops)
                        avg_entry = Decimal('0')
                    else:
                        # Position fully closed, reset everything
                        position_qty = Decimal('0')
                        cost_basis = Decimal('0')
                        avg_entry = Decimal('0')
                    
                    trade_label = "DEX_SELL" if event.trade_type == 'dex_sell' else "SELL"
                    logging.debug(f"{trade_label}: -{sell_qty} @ {price_kas:.12f} KAS (P&L: {pnl_this_sale:+.8f}) | Position: {position_qty}, Rebased Avg Entry: {avg_entry:.12f}")
                else:
                    trade_label = "DEX_SELL" if event.trade_type == 'dex_sell' else "SELL"
                    logging.warning(f"{trade_label} without position: {event.id} - Skipping")
            
            last_event_id = event.id
        
        # avg_entry_mc_kas will be calculated in get_position_metrics() based on current market cap
        # For now, set it to cost_basis as a fallback
        avg_entry_mc_kas = cost_basis
        
        result = {
            'qty_remaining': position_qty,
            'cost_basis_kas': cost_basis,
            'avg_entry_price_kas': avg_entry,
            'avg_entry_mc_kas': avg_entry_mc_kas,
            'realized_pnl_kas': realized_pnl,
            'last_trade_event_id': last_event_id
        }
        
        logging.info(f"Position computed for user {user_id} on token {token_id}: {result}")
        return result
    
    @staticmethod
    def _get_user_wallets(user):
        """Get all wallet addresses for a user (primary + verified linked wallets)"""
        wallet_addresses = [user.wallet_address.lower()]
        
        # Add verified linked wallets
        linked_wallets = LinkedWallet.query.filter_by(
            user_id=user.id,
            status='verified'
        ).all()
        
        for linked in linked_wallets:
            wallet_addresses.append(linked.wallet_address.lower())
        
        logging.debug(f"User {user.id} has {len(wallet_addresses)} wallet(s): {wallet_addresses}")
        return wallet_addresses
    
    @staticmethod
    def upsert_position(user, token, metrics=None):
        """
        Update or insert position cache in database
        
        Args:
            user: User object or user_id
            token: Token object or token_id
            metrics: Optional dict with computed metrics (if None, will compute)
        
        Returns:
            Position object
        """
        # Normalize inputs
        user_id = user.id if hasattr(user, 'id') else user
        token_id = token.id if hasattr(token, 'id') else token
        
        # Compute metrics if not provided
        if metrics is None:
            metrics = PositionService.compute_position(user, token)
            if not metrics:
                return None
        
        # CRITICAL VALIDATION: Prevent writing avg_entry_price_kas=0 when cost_basis>0
        # This can happen when trades are processed during errors (e.g., User import bug)
        # If cost_basis > 0 and qty_remaining > 0, then avg_entry MUST be cost_basis / qty
        # NOTE: qty_remaining is already in human-readable units (not wei), so no conversion needed
        if (metrics['avg_entry_price_kas'] == 0 and 
            metrics['cost_basis_kas'] > 0 and 
            metrics['qty_remaining'] > 0):
            
            metrics['avg_entry_price_kas'] = metrics['cost_basis_kas'] / metrics['qty_remaining']
            logging.warning(
                f"⚠️ Corrected zero avg_entry_price_kas: cost_basis={metrics['cost_basis_kas']} KAS, "
                f"qty={metrics['qty_remaining']} → avg_entry={metrics['avg_entry_price_kas']:.12f} KAS"
            )
        
        # Find existing position or create new
        position = Position.query.filter_by(
            user_id=user_id,
            token_id=token_id
        ).first()
        
        if position:
            # Update existing
            position.qty_remaining = metrics['qty_remaining']
            position.cost_basis_kas = metrics['cost_basis_kas']
            position.avg_entry_price_kas = metrics['avg_entry_price_kas']
            position.realized_pnl_kas = metrics['realized_pnl_kas']
            position.last_trade_event_id = metrics['last_trade_event_id']
            position.updated_at = datetime.now(timezone.utc)
        else:
            # Create new
            position = Position(
                user_id=user_id,
                token_id=token_id,
                qty_remaining=metrics['qty_remaining'],
                cost_basis_kas=metrics['cost_basis_kas'],
                avg_entry_price_kas=metrics['avg_entry_price_kas'],
                realized_pnl_kas=metrics['realized_pnl_kas'],
                last_trade_event_id=metrics['last_trade_event_id']
            )
            db.session.add(position)
        
        db.session.commit()
        logging.info(f"Position upserted: user={user_id}, token={token_id}, qty={position.qty_remaining}")
        
        return position
    
    @staticmethod
    def get_position_metrics(user, token, current_price_kas=None, current_market_cap_kas=None):
        """
        Get position metrics with unrealized P&L calculation
        
        Args:
            user: User object or user_id
            token: Token object or token_id
            current_price_kas: Optional current price in KAS (for P&L calculation)
            current_market_cap_kas: Optional current market cap in KAS (for break-even MC calculation)
        
        Returns:
            dict with full position metrics including unrealized P&L
        """
        # Try to get from cache first
        user_id = user.id if hasattr(user, 'id') else user
        token_id = token.id if hasattr(token, 'id') else token
        
        position = Position.query.filter_by(
            user_id=user_id,
            token_id=token_id
        ).first()
        
        # If no cached position, compute fresh
        if not position:
            metrics = PositionService.compute_position(user, token)
            if not metrics:
                return None
            # Don't return early - allow break-even MC calculation below
        else:
            # Use cached values
            metrics = {
                'qty_remaining': position.qty_remaining,
                'cost_basis_kas': position.cost_basis_kas,
                'avg_entry_price_kas': position.avg_entry_price_kas,
                'realized_pnl_kas': position.realized_pnl_kas,
                'last_trade_event_id': position.last_trade_event_id
            }
        
        # Calculate break-even market cap if current market cap is provided
        if current_market_cap_kas and current_price_kas and metrics['avg_entry_price_kas'] > 0:
            # Break-even MC in KAS = (avg_entry_price / current_price) × current_market_cap
            ratio = metrics['avg_entry_price_kas'] / current_price_kas
            breakeven_mc_kas = ratio * current_market_cap_kas
            
            # Convert to USD for chart display (chart shows MC in $)
            from services.kas_oracle import oracle
            kas_price_usd = oracle.get_kas_price()
            metrics['avg_entry_mc_kas'] = breakeven_mc_kas * Decimal(str(kas_price_usd))
            
            logging.info(
                f"Break-even MC: {breakeven_mc_kas:.2f} KAS × ${kas_price_usd:.4f} = ${metrics['avg_entry_mc_kas']:.2f} USD"
            )
        else:
            # Fallback: convert cost basis to USD
            from services.kas_oracle import oracle
            kas_price_usd = oracle.get_kas_price()
            metrics['avg_entry_mc_kas'] = metrics['cost_basis_kas'] * Decimal(str(kas_price_usd))
            logging.warning(
                f"Using cost_basis as avg_entry_mc_kas fallback: "
                f"{metrics['cost_basis_kas']} KAS × ${kas_price_usd} = ${metrics['avg_entry_mc_kas']:.2f} USD"
            )
        
        # Calculate unrealized P&L if current price provided
        if current_price_kas is not None and metrics['qty_remaining'] > 0:
            current_price = Decimal(str(current_price_kas))
            unrealized_pnl_kas = (current_price - metrics['avg_entry_price_kas']) * metrics['qty_remaining']
            unrealized_pnl_pct = ((current_price - metrics['avg_entry_price_kas']) / metrics['avg_entry_price_kas'] * 100) if metrics['avg_entry_price_kas'] > 0 else Decimal('0')
            
            metrics['unrealized_pnl_kas'] = unrealized_pnl_kas
            metrics['unrealized_pnl_pct'] = unrealized_pnl_pct
        else:
            metrics['unrealized_pnl_kas'] = Decimal('0')
            metrics['unrealized_pnl_pct'] = Decimal('0')
        
        return metrics

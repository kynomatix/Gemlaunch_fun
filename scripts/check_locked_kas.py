"""
Script to check locked KAS across all GraduationControllers
Used by admin panel recovery system
"""

from web3 import Web3

# Kasplex Testnet RPC
RPC_URL = 'https://rpc.kasplextest.xyz'
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Known GraduationControllers
GRADUATION_CONTROLLERS = {
    'V6':  '0xBbfdF7341aaF104D259876972844EBF9795b9C4C',
    'V9':  '0xaC022Ab0860D3D7D5A8738cd6BF58090117CC7f6',
    'V10': '0x7384F95729Ff5c2B2BFe4Cc101139a13A85a66e9',
    'V11': '0xd0Ca76Dc29714Ef316a6aacCAC8837c3119439e0',
    'V12': '0xD7B75104f005DFC9dE004fdb97399444752d66D3',
    'V13': '0xf04aB5deE799DDb217a03bF07fFf4dDf541dD9f1',
}

# Treasury wallet (owner of all GCs)
TREASURY = '0xe281e4776FB5De20817D0bbC72B0C4b955565619'

def get_recovery_info():
    """Get information about recoverable KAS"""
    
    total_locked = 0
    recoverable = 0
    gc_list = []
    
    owner_selector = w3.keccak(text='owner()')[:4].hex()
    
    for version, gc_addr in GRADUATION_CONTROLLERS.items():
        try:
            gc_checksum = Web3.to_checksum_address(gc_addr)
            
            # Get balance
            balance_wei = w3.eth.get_balance(gc_checksum)
            balance_kas = float(Web3.from_wei(balance_wei, 'ether'))
            
            # Get owner
            result = w3.eth.call({'to': gc_checksum, 'data': owner_selector})
            owner = Web3.to_checksum_address('0x' + result.hex()[-40:])
            
            total_locked += balance_kas
            
            gc_info = {
                'version': version,
                'address': gc_addr,
                'balance': balance_kas,
                'owner': owner,
                'recoverable': owner.lower() == TREASURY.lower()
            }
            
            if gc_info['recoverable']:
                recoverable += balance_kas
            
            gc_list.append(gc_info)
            
        except Exception as e:
            print(f"Error checking {version}: {e}")
    
    return {
        'success': True,
        'total_locked_kas': total_locked,
        'recoverable_kas': recoverable,
        'graduation_controllers': [gc for gc in gc_list if gc['balance'] > 0 and gc['recoverable']],
        'treasury_address': TREASURY
    }

if __name__ == '__main__':
    import json
    result = get_recovery_info()
    print(json.dumps(result, indent=2))

--
-- PostgreSQL database dump
--

-- Dumped from database version 16.9 (415ebe8)
-- Dumped by pg_dump version 17.5

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: accolade_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accolade_logs (
    id integer NOT NULL,
    user_id integer,
    achievement_id integer,
    awarded_by character varying(128),
    reason text,
    points_override integer,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: accolade_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.accolade_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: accolade_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.accolade_logs_id_seq OWNED BY public.accolade_logs.id;


--
-- Name: achievement; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.achievement (
    id integer NOT NULL,
    name character varying(128) NOT NULL,
    description text,
    icon character varying(128),
    category character varying(64),
    requirement_type character varying(64),
    requirement_value numeric(20,8),
    gem_points_reward integer,
    is_active boolean,
    created_at timestamp without time zone
);


--
-- Name: achievement_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.achievement_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: achievement_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.achievement_id_seq OWNED BY public.achievement.id;


--
-- Name: activity; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.activity (
    id integer NOT NULL,
    user_id integer NOT NULL,
    activity_type character varying(64) NOT NULL,
    title character varying(256) NOT NULL,
    description text,
    token_id integer,
    trade_id integer,
    achievement_id integer,
    points_earned integer,
    is_public boolean,
    created_at timestamp without time zone
);


--
-- Name: activity_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.activity_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: activity_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.activity_id_seq OWNED BY public.activity.id;


--
-- Name: admin_users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admin_users (
    id integer NOT NULL,
    username character varying(64) NOT NULL,
    password_hash character varying(256) NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: admin_users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.admin_users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: admin_users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.admin_users_id_seq OWNED BY public.admin_users.id;


--
-- Name: airdrop; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.airdrop (
    id integer NOT NULL,
    token_id integer NOT NULL,
    creator_id integer NOT NULL,
    airdrop_type character varying(32) NOT NULL,
    total_amount numeric(30,0) NOT NULL,
    parameters json,
    status character varying(32),
    recipient_count integer,
    distributed_amount numeric(30,0),
    tx_hash character varying(128),
    created_at timestamp without time zone,
    completed_at timestamp without time zone,
    distribution_type character varying(16) DEFAULT 'claim'::character varying,
    withdrawal_tx character varying(128),
    approval_tx character varying(128),
    distribution_tx character varying(128)
);


--
-- Name: airdrop_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.airdrop_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: airdrop_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.airdrop_id_seq OWNED BY public.airdrop.id;


--
-- Name: airdrop_recipient; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.airdrop_recipient (
    id integer NOT NULL,
    airdrop_id integer NOT NULL,
    user_id integer NOT NULL,
    amount_received numeric(30,0) NOT NULL,
    is_claimed boolean,
    claimed_at timestamp without time zone,
    claim_tx_hash character varying(128),
    created_at timestamp without time zone
);


--
-- Name: airdrop_recipient_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.airdrop_recipient_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: airdrop_recipient_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.airdrop_recipient_id_seq OWNED BY public.airdrop_recipient.id;


--
-- Name: anti_bot_fee_tracker; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.anti_bot_fee_tracker (
    id integer NOT NULL,
    token_id integer NOT NULL,
    trade_event_id integer NOT NULL,
    total_anti_bot_fee numeric(20,8) NOT NULL,
    airdrop_treasury_amount numeric(20,8) NOT NULL,
    platform_dev_amount numeric(20,8) NOT NULL,
    tx_hash character varying(128) NOT NULL,
    block_number integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    created_at timestamp without time zone
);


--
-- Name: anti_bot_fee_tracker_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.anti_bot_fee_tracker_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: anti_bot_fee_tracker_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.anti_bot_fee_tracker_id_seq OWNED BY public.anti_bot_fee_tracker.id;


--
-- Name: chat_message; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_message (
    id integer NOT NULL,
    token_id integer NOT NULL,
    user_id integer NOT NULL,
    content text NOT NULL,
    message_type character varying(32),
    is_pinned boolean,
    is_deleted boolean,
    is_holders_only boolean,
    love_count integer,
    reply_count integer,
    created_at timestamp without time zone,
    edited_at timestamp without time zone,
    reply_to_id integer
);


--
-- Name: chat_message_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chat_message_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: chat_message_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chat_message_id_seq OWNED BY public.chat_message.id;


--
-- Name: claim_ownership_challenge; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.claim_ownership_challenge (
    id integer NOT NULL,
    claimant_user_id integer NOT NULL,
    disputed_wallet_address character varying(128) NOT NULL,
    legacy_user_id integer NOT NULL,
    nonce character varying(128) NOT NULL,
    challenge_message text NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    used boolean NOT NULL,
    created_at timestamp without time zone
);


--
-- Name: TABLE claim_ownership_challenge; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.claim_ownership_challenge IS 'DEPRECATED: This table is no longer actively used. The functionality has been replaced by the transfer_request table which provides a cleaner approval flow. This table is preserved for historical data only (14 records as of October 2025). Do not insert new records into this table.';


--
-- Name: claim_ownership_challenge_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.claim_ownership_challenge_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: claim_ownership_challenge_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.claim_ownership_challenge_id_seq OWNED BY public.claim_ownership_challenge.id;


--
-- Name: connected_wallet; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.connected_wallet (
    id integer NOT NULL,
    user_id integer NOT NULL,
    wallet_address character varying(128) NOT NULL,
    wallet_type character varying(32) NOT NULL,
    wallet_label character varying(64),
    is_primary boolean,
    is_verified boolean,
    connected_at timestamp without time zone,
    last_used timestamp without time zone
);


--
-- Name: connected_wallet_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.connected_wallet_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: connected_wallet_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.connected_wallet_id_seq OWNED BY public.connected_wallet.id;


--
-- Name: holding; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.holding (
    id integer NOT NULL,
    user_id integer NOT NULL,
    token_id integer NOT NULL,
    token_amount numeric(30,0),
    average_price numeric(20,12),
    total_invested numeric(20,8),
    first_purchase timestamp without time zone,
    last_trade timestamp without time zone
);


--
-- Name: holding_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.holding_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: holding_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.holding_id_seq OWNED BY public.holding.id;


--
-- Name: linked_wallet; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.linked_wallet (
    id integer NOT NULL,
    user_id integer NOT NULL,
    wallet_address character varying(128) NOT NULL,
    wallet_label character varying(128),
    signature_payload text,
    last_verified_at timestamp without time zone,
    status character varying(32) NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: linked_wallet_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.linked_wallet_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: linked_wallet_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.linked_wallet_id_seq OWNED BY public.linked_wallet.id;


--
-- Name: message_reaction; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.message_reaction (
    id integer NOT NULL,
    message_id integer NOT NULL,
    user_id integer NOT NULL,
    reaction_type character varying(32),
    created_at timestamp without time zone
);


--
-- Name: message_reaction_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.message_reaction_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: message_reaction_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.message_reaction_id_seq OWNED BY public.message_reaction.id;


--
-- Name: partner_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.partner_tokens (
    id integer NOT NULL,
    token_id integer,
    stake_amount numeric(20,8) DEFAULT 0,
    lockup_days integer DEFAULT 30,
    point_multiplier double precision DEFAULT 1.5,
    is_active boolean DEFAULT true,
    partnership_started timestamp without time zone DEFAULT now(),
    partnership_ends timestamp without time zone
);


--
-- Name: partner_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.partner_tokens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: partner_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.partner_tokens_id_seq OWNED BY public.partner_tokens.id;


--
-- Name: pending_transaction; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pending_transaction (
    id integer NOT NULL,
    tx_hash character varying(128) NOT NULL,
    tx_type character varying(50),
    user_address character varying(128),
    token_id integer,
    status character varying(20),
    created_at timestamp without time zone,
    confirmed_at timestamp without time zone,
    block_number integer,
    gas_used integer,
    error_message text
);


--
-- Name: pending_transaction_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pending_transaction_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pending_transaction_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pending_transaction_id_seq OWNED BY public.pending_transaction.id;


--
-- Name: platform_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.platform_settings (
    id integer NOT NULL,
    graduation_threshold_usd numeric(20,2),
    network character varying(32),
    updated_at timestamp without time zone,
    updated_by character varying(128)
);


--
-- Name: platform_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.platform_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: platform_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.platform_settings_id_seq OWNED BY public.platform_settings.id;


--
-- Name: poll; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.poll (
    id integer NOT NULL,
    token_id integer NOT NULL,
    creator_id integer NOT NULL,
    question character varying(500) NOT NULL,
    poll_type character varying(32),
    min_tokens_to_vote numeric(30,0),
    vote_cost numeric(30,0),
    is_active boolean,
    is_anonymous boolean,
    created_at timestamp without time zone,
    ends_at timestamp without time zone
);


--
-- Name: poll_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.poll_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: poll_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.poll_id_seq OWNED BY public.poll.id;


--
-- Name: poll_option; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.poll_option (
    id integer NOT NULL,
    poll_id integer NOT NULL,
    option_text character varying(200) NOT NULL,
    vote_count integer
);


--
-- Name: poll_option_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.poll_option_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: poll_option_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.poll_option_id_seq OWNED BY public.poll_option.id;


--
-- Name: poll_vote; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.poll_vote (
    id integer NOT NULL,
    poll_id integer NOT NULL,
    option_id integer NOT NULL,
    user_id integer NOT NULL,
    vote_weight numeric(20,8),
    created_at timestamp without time zone,
    burn_tx_hash character varying(128)
);


--
-- Name: poll_vote_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.poll_vote_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: poll_vote_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.poll_vote_id_seq OWNED BY public.poll_vote.id;


--
-- Name: position; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."position" (
    id integer NOT NULL,
    user_id integer NOT NULL,
    token_id integer NOT NULL,
    qty_remaining numeric(45,18) NOT NULL,
    cost_basis_kas numeric(30,8) NOT NULL,
    avg_entry_price_kas numeric(40,20) NOT NULL,
    realized_pnl_kas numeric(20,8),
    last_trade_event_id integer,
    updated_at timestamp without time zone
);


--
-- Name: position_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.position_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: position_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.position_id_seq OWNED BY public."position".id;


--
-- Name: referral; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.referral (
    id integer NOT NULL,
    referrer_id integer NOT NULL,
    referee_id integer,
    referral_code character varying(32) NOT NULL,
    referral_link character varying(256),
    status character varying(32),
    clicks integer,
    qualified_signups integer,
    points_earned integer,
    is_rewarded boolean,
    created_at timestamp without time zone,
    completed_at timestamp without time zone
);


--
-- Name: referral_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.referral_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: referral_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.referral_id_seq OWNED BY public.referral.id;


--
-- Name: reserve_distribution; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reserve_distribution (
    id integer NOT NULL,
    token_id integer NOT NULL,
    recipient_wallet character varying(128) NOT NULL,
    allocation_type character varying(32) NOT NULL,
    amount numeric(30,0) NOT NULL,
    tx_hash character varying(128),
    distributed_at timestamp without time zone,
    created_at timestamp without time zone
);


--
-- Name: reserve_distribution_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reserve_distribution_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: reserve_distribution_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reserve_distribution_id_seq OWNED BY public.reserve_distribution.id;


--
-- Name: token; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.token (
    id integer NOT NULL,
    name character varying(128) NOT NULL,
    symbol character varying(16) NOT NULL,
    description text,
    image_url character varying(512),
    total_supply numeric(30,0),
    reserved_tokens numeric(30,0),
    reserved_percentage double precision,
    contract_address character varying(128),
    deployment_tx character varying(128),
    deployment_status character varying(32),
    current_market_cap numeric(20,8),
    current_price numeric(20,12),
    circulating_supply numeric(30,0),
    trading_volume_24h numeric(20,8),
    kas_reserve numeric(20,8),
    token_reserve numeric(30,0),
    is_graduated boolean,
    graduation_tx character varying(128),
    graduated_at timestamp without time zone,
    creator_id integer NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    view_count integer,
    trade_count integer,
    holder_count integer,
    website character varying(512),
    twitter character varying(512),
    telegram character varying(512),
    anti_bot_enabled boolean DEFAULT false,
    airdrops_allocation double precision DEFAULT 33.0,
    marketing_allocation double precision DEFAULT 33.0,
    team_allocation double precision DEFAULT 34.0,
    total_airdropped numeric(30,0) DEFAULT 0,
    creator_fees_accumulated numeric(20,8) DEFAULT 0,
    deployment_block_number integer,
    nft_position_id integer,
    liquidity_pool_address character varying(128),
    ipfs_image_hash character varying(128),
    ipfs_metadata_hash character varying(128),
    ipfs_image_url character varying(256),
    ipfs_metadata_url character varying(256),
    marketing_vesting_address character varying(255),
    team_vesting_address character varying(255),
    airdrop_vesting_address character varying(255),
    vesting_deployment_tx character varying(128),
    vesting_deployment_status character varying(32) DEFAULT 'none'::character varying,
    marketing_next_claim_available timestamp without time zone,
    team_next_claim_available timestamp without time zone,
    airdrop_next_claim_available timestamp without time zone,
    market_cap_ath numeric(20,8) DEFAULT 1000,
    graduation_status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    graduation_initiated_at timestamp with time zone,
    graduation_completed_at timestamp with time zone,
    graduation_initiation_tx character varying(128),
    graduation_completion_tx character varying(128),
    dex_pool_address character varying(128),
    dex_pool_fee_tier integer,
    lp_nft_position_id bigint,
    lp_liquidity_kas numeric(36,18),
    lp_liquidity_tokens numeric(36,18),
    burned_token_amount numeric(36,18),
    lp_fees_collected_kas numeric(36,18) DEFAULT 0,
    last_lp_fee_collection timestamp with time zone,
    last_indexed_block integer,
    is_visible boolean DEFAULT true,
    graduation_disabled boolean DEFAULT false,
    categories text DEFAULT '["Community"]'::text
);


--
-- Name: token_accolade; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.token_accolade (
    id integer NOT NULL,
    token_id integer NOT NULL,
    name character varying(128) NOT NULL,
    description text,
    icon character varying(128),
    category character varying(64),
    requirement_type character varying(64),
    requirement_value numeric(20,8),
    points_reward integer,
    is_active boolean,
    is_pro_only boolean,
    awards_leaderboard_points boolean,
    created_at timestamp without time zone
);


--
-- Name: token_accolade_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.token_accolade_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: token_accolade_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.token_accolade_id_seq OWNED BY public.token_accolade.id;


--
-- Name: token_engagement; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.token_engagement (
    id integer NOT NULL,
    user_id integer NOT NULL,
    token_id integer NOT NULL,
    community_points integer,
    messages_sent integer,
    trades_count integer,
    total_traded_volume numeric(20,8),
    polls_created integer,
    polls_voted integer,
    spotlight_messages integer,
    current_balance numeric(30,0),
    first_acquired_at timestamp without time zone,
    last_activity_at timestamp without time zone,
    created_at timestamp without time zone,
    reactions_received integer DEFAULT 0,
    buy_count integer DEFAULT 0,
    sell_count integer DEFAULT 0,
    holding_days integer DEFAULT 0,
    diamond_hands_score integer DEFAULT 0,
    milestone_30d_awarded boolean DEFAULT false,
    milestone_60d_awarded boolean DEFAULT false,
    milestone_90d_awarded boolean DEFAULT false,
    milestone_180d_awarded boolean DEFAULT false,
    milestone_365d_awarded boolean DEFAULT false
);


--
-- Name: token_engagement_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.token_engagement_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: token_engagement_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.token_engagement_id_seq OWNED BY public.token_engagement.id;


--
-- Name: token_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.token_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: token_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.token_id_seq OWNED BY public.token.id;


--
-- Name: token_leaderboard; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.token_leaderboard (
    id integer NOT NULL,
    token_id integer NOT NULL,
    user_id integer NOT NULL,
    points integer,
    rank integer,
    messages_sent integer,
    reactions_given integer,
    reactions_received integer,
    polls_created integer,
    votes_cast integer,
    accolades_earned integer,
    first_activity timestamp without time zone,
    last_activity timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: token_leaderboard_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.token_leaderboard_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: token_leaderboard_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.token_leaderboard_id_seq OWNED BY public.token_leaderboard.id;


--
-- Name: token_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.token_settings (
    id integer NOT NULL,
    token_id integer NOT NULL,
    holders_only_chat boolean,
    min_tokens_to_chat numeric(30,0),
    min_tokens_for_spotlight numeric(30,0),
    min_tokens_to_create_poll numeric(30,0),
    poll_creation_cost numeric(30,0),
    dao_voting_threshold numeric(30,0),
    treasury_allocation_percent double precision,
    airdrop_pool_percent double precision,
    liquidity_rewards_enabled boolean,
    chat_enabled boolean,
    polls_enabled boolean,
    accolades_enabled boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: token_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.token_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: token_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.token_settings_id_seq OWNED BY public.token_settings.id;


--
-- Name: trade; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trade (
    id integer NOT NULL,
    user_id integer NOT NULL,
    token_id integer NOT NULL,
    trade_type character varying(16) NOT NULL,
    kas_amount numeric(20,8) NOT NULL,
    token_amount numeric(30,0) NOT NULL,
    price_per_token numeric(20,12) NOT NULL,
    market_cap_before numeric(20,8),
    market_cap_after numeric(20,8),
    tx_hash character varying(128),
    tx_status character varying(32),
    platform_fee numeric(20,8),
    created_at timestamp without time zone,
    confirmed_at timestamp without time zone
);


--
-- Name: trade_event; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trade_event (
    id integer NOT NULL,
    token_id integer NOT NULL,
    user_wallet_address character varying(128) NOT NULL,
    trade_type character varying(16) NOT NULL,
    kas_amount numeric(20,8) NOT NULL,
    token_amount numeric(30,0) NOT NULL,
    platform_fee numeric(20,8),
    creator_fee numeric(20,8),
    anti_bot_fee numeric(20,8),
    tx_hash character varying(128) NOT NULL,
    block_number integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    created_at timestamp without time zone,
    log_index integer DEFAULT 0 NOT NULL,
    is_dex_trade boolean DEFAULT false
);


--
-- Name: trade_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.trade_event_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: trade_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.trade_event_id_seq OWNED BY public.trade_event.id;


--
-- Name: trade_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.trade_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: trade_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.trade_id_seq OWNED BY public.trade.id;


--
-- Name: transfer_request; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transfer_request (
    id integer NOT NULL,
    requester_id integer NOT NULL,
    owner_id integer NOT NULL,
    wallet_address character varying(128) NOT NULL,
    status character varying(32) NOT NULL,
    nonce character varying(128) NOT NULL,
    created_at timestamp without time zone,
    expires_at timestamp without time zone NOT NULL
);


--
-- Name: transfer_request_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transfer_request_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transfer_request_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transfer_request_id_seq OWNED BY public.transfer_request.id;


--
-- Name: trend_cache; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trend_cache (
    id integer NOT NULL,
    cache_type character varying(32) NOT NULL,
    trends_data json,
    scored_trends json,
    kaspa_memes json,
    scraped_at timestamp without time zone,
    expires_at timestamp without time zone,
    is_valid boolean,
    usage_count integer
);


--
-- Name: trend_cache_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.trend_cache_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: trend_cache_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.trend_cache_id_seq OWNED BY public.trend_cache.id;


--
-- Name: user; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."user" (
    id integer NOT NULL,
    wallet_address character varying(128),
    created_at timestamp without time zone,
    last_seen timestamp without time zone,
    is_active boolean,
    gem_points integer,
    total_tokens_created integer,
    total_trading_volume numeric(20,8),
    display_name character varying(64),
    wallet_type character varying(32),
    total_graduated_tokens integer DEFAULT 0,
    total_trades_count integer DEFAULT 0,
    total_messages_sent integer DEFAULT 0,
    longest_holding_days integer DEFAULT 0,
    archived boolean DEFAULT false,
    claimed_by integer,
    archived_at timestamp without time zone
);


--
-- Name: user_achievement; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_achievement (
    id integer NOT NULL,
    user_id integer NOT NULL,
    achievement_id integer NOT NULL,
    earned_at timestamp without time zone
);


--
-- Name: user_achievement_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_achievement_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_achievement_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_achievement_id_seq OWNED BY public.user_achievement.id;


--
-- Name: user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_id_seq OWNED BY public."user".id;


--
-- Name: user_profile; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_profile (
    id integer NOT NULL,
    user_id integer NOT NULL,
    bio text,
    username character varying(64),
    twitter_handle character varying(64),
    telegram_handle character varying(64),
    discord_handle character varying(64),
    is_twitter_verified boolean,
    is_telegram_verified boolean,
    account_type character varying(32),
    member_since timestamp without time zone,
    is_profile_public boolean,
    show_wallet_address boolean,
    avatar_path character varying(256),
    avatar_updated_at timestamp without time zone,
    twitter_user_id character varying(255),
    twitter_verified_at timestamp without time zone
);


--
-- Name: user_profile_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_profile_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_profile_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_profile_id_seq OWNED BY public.user_profile.id;


--
-- Name: user_token_accolade; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_token_accolade (
    id integer NOT NULL,
    user_id integer NOT NULL,
    accolade_id integer NOT NULL,
    token_id integer NOT NULL,
    earned_at timestamp without time zone,
    points_awarded integer
);


--
-- Name: user_token_accolade_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_token_accolade_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_token_accolade_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_token_accolade_id_seq OWNED BY public.user_token_accolade.id;


--
-- Name: wallet_verification_challenge; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wallet_verification_challenge (
    id integer NOT NULL,
    user_id integer NOT NULL,
    wallet_address character varying(128) NOT NULL,
    nonce character varying(128) NOT NULL,
    challenge_message text NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    used boolean NOT NULL,
    created_at timestamp without time zone
);


--
-- Name: wallet_verification_challenge_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wallet_verification_challenge_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: wallet_verification_challenge_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wallet_verification_challenge_id_seq OWNED BY public.wallet_verification_challenge.id;


--
-- Name: accolade_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accolade_logs ALTER COLUMN id SET DEFAULT nextval('public.accolade_logs_id_seq'::regclass);


--
-- Name: achievement id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.achievement ALTER COLUMN id SET DEFAULT nextval('public.achievement_id_seq'::regclass);


--
-- Name: activity id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity ALTER COLUMN id SET DEFAULT nextval('public.activity_id_seq'::regclass);


--
-- Name: admin_users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_users ALTER COLUMN id SET DEFAULT nextval('public.admin_users_id_seq'::regclass);


--
-- Name: airdrop id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.airdrop ALTER COLUMN id SET DEFAULT nextval('public.airdrop_id_seq'::regclass);


--
-- Name: airdrop_recipient id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.airdrop_recipient ALTER COLUMN id SET DEFAULT nextval('public.airdrop_recipient_id_seq'::regclass);


--
-- Name: anti_bot_fee_tracker id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.anti_bot_fee_tracker ALTER COLUMN id SET DEFAULT nextval('public.anti_bot_fee_tracker_id_seq'::regclass);


--
-- Name: chat_message id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_message ALTER COLUMN id SET DEFAULT nextval('public.chat_message_id_seq'::regclass);


--
-- Name: claim_ownership_challenge id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.claim_ownership_challenge ALTER COLUMN id SET DEFAULT nextval('public.claim_ownership_challenge_id_seq'::regclass);


--
-- Name: connected_wallet id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.connected_wallet ALTER COLUMN id SET DEFAULT nextval('public.connected_wallet_id_seq'::regclass);


--
-- Name: holding id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.holding ALTER COLUMN id SET DEFAULT nextval('public.holding_id_seq'::regclass);


--
-- Name: linked_wallet id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.linked_wallet ALTER COLUMN id SET DEFAULT nextval('public.linked_wallet_id_seq'::regclass);


--
-- Name: message_reaction id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_reaction ALTER COLUMN id SET DEFAULT nextval('public.message_reaction_id_seq'::regclass);


--
-- Name: partner_tokens id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.partner_tokens ALTER COLUMN id SET DEFAULT nextval('public.partner_tokens_id_seq'::regclass);


--
-- Name: pending_transaction id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pending_transaction ALTER COLUMN id SET DEFAULT nextval('public.pending_transaction_id_seq'::regclass);


--
-- Name: platform_settings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_settings ALTER COLUMN id SET DEFAULT nextval('public.platform_settings_id_seq'::regclass);


--
-- Name: poll id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.poll ALTER COLUMN id SET DEFAULT nextval('public.poll_id_seq'::regclass);


--
-- Name: poll_option id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.poll_option ALTER COLUMN id SET DEFAULT nextval('public.poll_option_id_seq'::regclass);


--
-- Name: poll_vote id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.poll_vote ALTER COLUMN id SET DEFAULT nextval('public.poll_vote_id_seq'::regclass);


--
-- Name: position id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."position" ALTER COLUMN id SET DEFAULT nextval('public.position_id_seq'::regclass);


--
-- Name: referral id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.referral ALTER COLUMN id SET DEFAULT nextval('public.referral_id_seq'::regclass);


--
-- Name: reserve_distribution id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reserve_distribution ALTER COLUMN id SET DEFAULT nextval('public.reserve_distribution_id_seq'::regclass);


--
-- Name: token id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token ALTER COLUMN id SET DEFAULT nextval('public.token_id_seq'::regclass);


--
-- Name: token_accolade id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_accolade ALTER COLUMN id SET DEFAULT nextval('public.token_accolade_id_seq'::regclass);


--
-- Name: token_engagement id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_engagement ALTER COLUMN id SET DEFAULT nextval('public.token_engagement_id_seq'::regclass);


--
-- Name: token_leaderboard id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_leaderboard ALTER COLUMN id SET DEFAULT nextval('public.token_leaderboard_id_seq'::regclass);


--
-- Name: token_settings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_settings ALTER COLUMN id SET DEFAULT nextval('public.token_settings_id_seq'::regclass);


--
-- Name: trade id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trade ALTER COLUMN id SET DEFAULT nextval('public.trade_id_seq'::regclass);


--
-- Name: trade_event id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trade_event ALTER COLUMN id SET DEFAULT nextval('public.trade_event_id_seq'::regclass);


--
-- Name: transfer_request id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_request ALTER COLUMN id SET DEFAULT nextval('public.transfer_request_id_seq'::regclass);


--
-- Name: trend_cache id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trend_cache ALTER COLUMN id SET DEFAULT nextval('public.trend_cache_id_seq'::regclass);


--
-- Name: user id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user" ALTER COLUMN id SET DEFAULT nextval('public.user_id_seq'::regclass);


--
-- Name: user_achievement id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_achievement ALTER COLUMN id SET DEFAULT nextval('public.user_achievement_id_seq'::regclass);


--
-- Name: user_profile id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profile ALTER COLUMN id SET DEFAULT nextval('public.user_profile_id_seq'::regclass);


--
-- Name: user_token_accolade id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_token_accolade ALTER COLUMN id SET DEFAULT nextval('public.user_token_accolade_id_seq'::regclass);


--
-- Name: wallet_verification_challenge id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wallet_verification_challenge ALTER COLUMN id SET DEFAULT nextval('public.wallet_verification_challenge_id_seq'::regclass);


--
-- Name: accolade_logs accolade_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accolade_logs
    ADD CONSTRAINT accolade_logs_pkey PRIMARY KEY (id);


--
-- Name: achievement achievement_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.achievement
    ADD CONSTRAINT achievement_pkey PRIMARY KEY (id);


--
-- Name: activity activity_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity
    ADD CONSTRAINT activity_pkey PRIMARY KEY (id);


--
-- Name: admin_users admin_users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_users
    ADD CONSTRAINT admin_users_pkey PRIMARY KEY (id);


--
-- Name: admin_users admin_users_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_users
    ADD CONSTRAINT admin_users_username_key UNIQUE (username);


--
-- Name: airdrop airdrop_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.airdrop
    ADD CONSTRAINT airdrop_pkey PRIMARY KEY (id);


--
-- Name: airdrop_recipient airdrop_recipient_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.airdrop_recipient
    ADD CONSTRAINT airdrop_recipient_pkey PRIMARY KEY (id);


--
-- Name: anti_bot_fee_tracker anti_bot_fee_tracker_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.anti_bot_fee_tracker
    ADD CONSTRAINT anti_bot_fee_tracker_pkey PRIMARY KEY (id);


--
-- Name: chat_message chat_message_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_message
    ADD CONSTRAINT chat_message_pkey PRIMARY KEY (id);


--
-- Name: claim_ownership_challenge claim_ownership_challenge_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.claim_ownership_challenge
    ADD CONSTRAINT claim_ownership_challenge_pkey PRIMARY KEY (id);


--
-- Name: connected_wallet connected_wallet_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.connected_wallet
    ADD CONSTRAINT connected_wallet_pkey PRIMARY KEY (id);


--
-- Name: holding holding_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.holding
    ADD CONSTRAINT holding_pkey PRIMARY KEY (id);


--
-- Name: linked_wallet linked_wallet_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.linked_wallet
    ADD CONSTRAINT linked_wallet_pkey PRIMARY KEY (id);


--
-- Name: message_reaction message_reaction_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_reaction
    ADD CONSTRAINT message_reaction_pkey PRIMARY KEY (id);


--
-- Name: partner_tokens partner_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.partner_tokens
    ADD CONSTRAINT partner_tokens_pkey PRIMARY KEY (id);


--
-- Name: partner_tokens partner_tokens_token_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.partner_tokens
    ADD CONSTRAINT partner_tokens_token_id_key UNIQUE (token_id);


--
-- Name: pending_transaction pending_transaction_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pending_transaction
    ADD CONSTRAINT pending_transaction_pkey PRIMARY KEY (id);


--
-- Name: platform_settings platform_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_settings
    ADD CONSTRAINT platform_settings_pkey PRIMARY KEY (id);


--
-- Name: poll_option poll_option_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.poll_option
    ADD CONSTRAINT poll_option_pkey PRIMARY KEY (id);


--
-- Name: poll poll_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.poll
    ADD CONSTRAINT poll_pkey PRIMARY KEY (id);


--
-- Name: poll_vote poll_vote_burn_tx_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.poll_vote
    ADD CONSTRAINT poll_vote_burn_tx_hash_key UNIQUE (burn_tx_hash);


--
-- Name: poll_vote poll_vote_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.poll_vote
    ADD CONSTRAINT poll_vote_pkey PRIMARY KEY (id);


--
-- Name: position position_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."position"
    ADD CONSTRAINT position_pkey PRIMARY KEY (id);


--
-- Name: referral referral_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.referral
    ADD CONSTRAINT referral_pkey PRIMARY KEY (id);


--
-- Name: reserve_distribution reserve_distribution_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reserve_distribution
    ADD CONSTRAINT reserve_distribution_pkey PRIMARY KEY (id);


--
-- Name: token_accolade token_accolade_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_accolade
    ADD CONSTRAINT token_accolade_pkey PRIMARY KEY (id);


--
-- Name: token_engagement token_engagement_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_engagement
    ADD CONSTRAINT token_engagement_pkey PRIMARY KEY (id);


--
-- Name: token_leaderboard token_leaderboard_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_leaderboard
    ADD CONSTRAINT token_leaderboard_pkey PRIMARY KEY (id);


--
-- Name: token token_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token
    ADD CONSTRAINT token_pkey PRIMARY KEY (id);


--
-- Name: token_settings token_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_settings
    ADD CONSTRAINT token_settings_pkey PRIMARY KEY (id);


--
-- Name: token_settings token_settings_token_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_settings
    ADD CONSTRAINT token_settings_token_id_key UNIQUE (token_id);


--
-- Name: trade_event trade_event_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trade_event
    ADD CONSTRAINT trade_event_pkey PRIMARY KEY (id);


--
-- Name: trade trade_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trade
    ADD CONSTRAINT trade_pkey PRIMARY KEY (id);


--
-- Name: trade trade_tx_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trade
    ADD CONSTRAINT trade_tx_hash_key UNIQUE (tx_hash);


--
-- Name: transfer_request transfer_request_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_request
    ADD CONSTRAINT transfer_request_pkey PRIMARY KEY (id);


--
-- Name: trend_cache trend_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trend_cache
    ADD CONSTRAINT trend_cache_pkey PRIMARY KEY (id);


--
-- Name: position uix_position_user_token; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."position"
    ADD CONSTRAINT uix_position_user_token UNIQUE (user_id, token_id);


--
-- Name: airdrop_recipient unique_airdrop_recipient; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.airdrop_recipient
    ADD CONSTRAINT unique_airdrop_recipient UNIQUE (airdrop_id, user_id);


--
-- Name: token_accolade unique_token_accolade; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_accolade
    ADD CONSTRAINT unique_token_accolade UNIQUE (token_id, name);


--
-- Name: token_leaderboard unique_token_user_leaderboard; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_leaderboard
    ADD CONSTRAINT unique_token_user_leaderboard UNIQUE (token_id, user_id);


--
-- Name: trade_event unique_tx_log_index; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trade_event
    ADD CONSTRAINT unique_tx_log_index UNIQUE (tx_hash, log_index);


--
-- Name: user_achievement unique_user_achievement; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_achievement
    ADD CONSTRAINT unique_user_achievement UNIQUE (user_id, achievement_id);


--
-- Name: message_reaction unique_user_message_reaction; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_reaction
    ADD CONSTRAINT unique_user_message_reaction UNIQUE (message_id, user_id);


--
-- Name: poll_vote unique_user_poll_vote; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.poll_vote
    ADD CONSTRAINT unique_user_poll_vote UNIQUE (poll_id, user_id);


--
-- Name: holding unique_user_token; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.holding
    ADD CONSTRAINT unique_user_token UNIQUE (user_id, token_id);


--
-- Name: user_token_accolade unique_user_token_accolade; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_token_accolade
    ADD CONSTRAINT unique_user_token_accolade UNIQUE (user_id, accolade_id);


--
-- Name: token_engagement unique_user_token_engagement; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_engagement
    ADD CONSTRAINT unique_user_token_engagement UNIQUE (user_id, token_id);


--
-- Name: connected_wallet unique_user_wallet; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.connected_wallet
    ADD CONSTRAINT unique_user_wallet UNIQUE (user_id, wallet_address);


--
-- Name: user_achievement user_achievement_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_achievement
    ADD CONSTRAINT user_achievement_pkey PRIMARY KEY (id);


--
-- Name: user user_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_pkey PRIMARY KEY (id);


--
-- Name: user_profile user_profile_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profile
    ADD CONSTRAINT user_profile_pkey PRIMARY KEY (id);


--
-- Name: user_profile user_profile_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profile
    ADD CONSTRAINT user_profile_user_id_key UNIQUE (user_id);


--
-- Name: user_profile user_profile_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profile
    ADD CONSTRAINT user_profile_username_key UNIQUE (username);


--
-- Name: user_token_accolade user_token_accolade_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_token_accolade
    ADD CONSTRAINT user_token_accolade_pkey PRIMARY KEY (id);


--
-- Name: wallet_verification_challenge wallet_verification_challenge_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wallet_verification_challenge
    ADD CONSTRAINT wallet_verification_challenge_pkey PRIMARY KEY (id);


--
-- Name: idx_claim_ownership_disputed_wallet; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_claim_ownership_disputed_wallet ON public.claim_ownership_challenge USING btree (disputed_wallet_address);


--
-- Name: idx_claim_ownership_nonce; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_claim_ownership_nonce ON public.claim_ownership_challenge USING btree (nonce);


--
-- Name: idx_pending_tx_status_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pending_tx_status_time ON public.pending_transaction USING btree (status, created_at);


--
-- Name: idx_poll_vote_burn_tx_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_poll_vote_burn_tx_hash ON public.poll_vote USING btree (burn_tx_hash);


--
-- Name: idx_position_user_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_position_user_token ON public."position" USING btree (user_id, token_id);


--
-- Name: idx_token_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_token_created_at ON public.token USING btree (created_at);


--
-- Name: idx_token_deployment_tx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_token_deployment_tx ON public.token USING btree (deployment_tx);


--
-- Name: idx_token_dex_pool; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_token_dex_pool ON public.token USING btree (dex_pool_address);


--
-- Name: idx_token_graduated_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_token_graduated_created ON public.token USING btree (is_graduated, created_at);


--
-- Name: idx_token_graduation_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_token_graduation_status ON public.token USING btree (graduation_status);


--
-- Name: idx_trade_event_block_number; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trade_event_block_number ON public.trade_event USING btree (block_number);


--
-- Name: idx_trade_event_dex_flag; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trade_event_dex_flag ON public.trade_event USING btree (is_dex_trade);


--
-- Name: idx_trade_event_token_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trade_event_token_time ON public.trade_event USING btree (token_id, "timestamp" DESC);


--
-- Name: ix_anti_bot_fee_tracker_block_number; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_anti_bot_fee_tracker_block_number ON public.anti_bot_fee_tracker USING btree (block_number);


--
-- Name: ix_anti_bot_fee_tracker_token_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_anti_bot_fee_tracker_token_id ON public.anti_bot_fee_tracker USING btree (token_id);


--
-- Name: ix_anti_bot_fee_tracker_tx_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_anti_bot_fee_tracker_tx_hash ON public.anti_bot_fee_tracker USING btree (tx_hash);


--
-- Name: ix_chat_message_token_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_message_token_id ON public.chat_message USING btree (token_id);


--
-- Name: ix_claim_ownership_challenge_disputed_wallet_address; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_claim_ownership_challenge_disputed_wallet_address ON public.claim_ownership_challenge USING btree (disputed_wallet_address);


--
-- Name: ix_claim_ownership_challenge_nonce; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_claim_ownership_challenge_nonce ON public.claim_ownership_challenge USING btree (nonce);


--
-- Name: ix_connected_wallet_wallet_address; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_connected_wallet_wallet_address ON public.connected_wallet USING btree (wallet_address);


--
-- Name: ix_linked_wallet_wallet_address; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_linked_wallet_wallet_address ON public.linked_wallet USING btree (wallet_address);


--
-- Name: ix_pending_transaction_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pending_transaction_created_at ON public.pending_transaction USING btree (created_at);


--
-- Name: ix_pending_transaction_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pending_transaction_status ON public.pending_transaction USING btree (status);


--
-- Name: ix_pending_transaction_token_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pending_transaction_token_id ON public.pending_transaction USING btree (token_id);


--
-- Name: ix_pending_transaction_tx_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_pending_transaction_tx_hash ON public.pending_transaction USING btree (tx_hash);


--
-- Name: ix_pending_transaction_user_address; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pending_transaction_user_address ON public.pending_transaction USING btree (user_address);


--
-- Name: ix_poll_token_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_poll_token_id ON public.poll USING btree (token_id);


--
-- Name: ix_position_token_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_position_token_id ON public."position" USING btree (token_id);


--
-- Name: ix_position_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_position_user_id ON public."position" USING btree (user_id);


--
-- Name: ix_referral_referral_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_referral_referral_code ON public.referral USING btree (referral_code);


--
-- Name: ix_reserve_distribution_recipient_wallet; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reserve_distribution_recipient_wallet ON public.reserve_distribution USING btree (recipient_wallet);


--
-- Name: ix_token_accolade_token_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_token_accolade_token_id ON public.token_accolade USING btree (token_id);


--
-- Name: ix_token_contract_address; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_token_contract_address ON public.token USING btree (contract_address);


--
-- Name: ix_token_leaderboard_token_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_token_leaderboard_token_id ON public.token_leaderboard USING btree (token_id);


--
-- Name: ix_token_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_token_symbol ON public.token USING btree (symbol);


--
-- Name: ix_trade_event_block_number; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trade_event_block_number ON public.trade_event USING btree (block_number);


--
-- Name: ix_trade_event_token_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trade_event_token_id ON public.trade_event USING btree (token_id);


--
-- Name: ix_trade_event_tx_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_trade_event_tx_hash ON public.trade_event USING btree (tx_hash);


--
-- Name: ix_trade_event_user_wallet_address; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trade_event_user_wallet_address ON public.trade_event USING btree (user_wallet_address);


--
-- Name: ix_transfer_request_nonce; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_transfer_request_nonce ON public.transfer_request USING btree (nonce);


--
-- Name: ix_transfer_request_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transfer_request_owner_id ON public.transfer_request USING btree (owner_id);


--
-- Name: ix_transfer_request_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transfer_request_status ON public.transfer_request USING btree (status);


--
-- Name: ix_transfer_request_wallet_address; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transfer_request_wallet_address ON public.transfer_request USING btree (wallet_address);


--
-- Name: ix_trend_cache_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trend_cache_expires_at ON public.trend_cache USING btree (expires_at);


--
-- Name: ix_trend_cache_scraped_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trend_cache_scraped_at ON public.trend_cache USING btree (scraped_at);


--
-- Name: ix_user_wallet_address; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_user_wallet_address ON public."user" USING btree (wallet_address);


--
-- Name: ix_wallet_verification_challenge_nonce; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_wallet_verification_challenge_nonce ON public.wallet_verification_challenge USING btree (nonce);


--
-- Name: ix_wallet_verification_challenge_wallet_address; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_wallet_verification_challenge_wallet_address ON public.wallet_verification_challenge USING btree (wallet_address);


--
-- Name: accolade_logs accolade_logs_achievement_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accolade_logs
    ADD CONSTRAINT accolade_logs_achievement_id_fkey FOREIGN KEY (achievement_id) REFERENCES public.achievement(id);


--
-- Name: accolade_logs accolade_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accolade_logs
    ADD CONSTRAINT accolade_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: activity activity_achievement_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity
    ADD CONSTRAINT activity_achievement_id_fkey FOREIGN KEY (achievement_id) REFERENCES public.achievement(id);


--
-- Name: activity activity_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity
    ADD CONSTRAINT activity_token_id_fkey FOREIGN KEY (token_id) REFERENCES public.token(id);


--
-- Name: activity activity_trade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity
    ADD CONSTRAINT activity_trade_id_fkey FOREIGN KEY (trade_id) REFERENCES public.trade(id);


--
-- Name: activity activity_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity
    ADD CONSTRAINT activity_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: airdrop airdrop_creator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.airdrop
    ADD CONSTRAINT airdrop_creator_id_fkey FOREIGN KEY (creator_id) REFERENCES public."user"(id);


--
-- Name: airdrop_recipient airdrop_recipient_airdrop_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.airdrop_recipient
    ADD CONSTRAINT airdrop_recipient_airdrop_id_fkey FOREIGN KEY (airdrop_id) REFERENCES public.airdrop(id);


--
-- Name: airdrop_recipient airdrop_recipient_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.airdrop_recipient
    ADD CONSTRAINT airdrop_recipient_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: airdrop airdrop_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.airdrop
    ADD CONSTRAINT airdrop_token_id_fkey FOREIGN KEY (token_id) REFERENCES public.token(id);


--
-- Name: anti_bot_fee_tracker anti_bot_fee_tracker_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.anti_bot_fee_tracker
    ADD CONSTRAINT anti_bot_fee_tracker_token_id_fkey FOREIGN KEY (token_id) REFERENCES public.token(id);


--
-- Name: anti_bot_fee_tracker anti_bot_fee_tracker_trade_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.anti_bot_fee_tracker
    ADD CONSTRAINT anti_bot_fee_tracker_trade_event_id_fkey FOREIGN KEY (trade_event_id) REFERENCES public.trade_event(id);


--
-- Name: chat_message chat_message_reply_to_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_message
    ADD CONSTRAINT chat_message_reply_to_id_fkey FOREIGN KEY (reply_to_id) REFERENCES public.chat_message(id);


--
-- Name: chat_message chat_message_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_message
    ADD CONSTRAINT chat_message_token_id_fkey FOREIGN KEY (token_id) REFERENCES public.token(id);


--
-- Name: chat_message chat_message_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_message
    ADD CONSTRAINT chat_message_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: claim_ownership_challenge claim_ownership_challenge_claimant_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.claim_ownership_challenge
    ADD CONSTRAINT claim_ownership_challenge_claimant_user_id_fkey FOREIGN KEY (claimant_user_id) REFERENCES public."user"(id);


--
-- Name: claim_ownership_challenge claim_ownership_challenge_legacy_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.claim_ownership_challenge
    ADD CONSTRAINT claim_ownership_challenge_legacy_user_id_fkey FOREIGN KEY (legacy_user_id) REFERENCES public."user"(id);


--
-- Name: connected_wallet connected_wallet_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.connected_wallet
    ADD CONSTRAINT connected_wallet_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: holding holding_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.holding
    ADD CONSTRAINT holding_token_id_fkey FOREIGN KEY (token_id) REFERENCES public.token(id);


--
-- Name: holding holding_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.holding
    ADD CONSTRAINT holding_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: linked_wallet linked_wallet_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.linked_wallet
    ADD CONSTRAINT linked_wallet_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: message_reaction message_reaction_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_reaction
    ADD CONSTRAINT message_reaction_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.chat_message(id) ON DELETE CASCADE;


--
-- Name: message_reaction message_reaction_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_reaction
    ADD CONSTRAINT message_reaction_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: partner_tokens partner_tokens_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.partner_tokens
    ADD CONSTRAINT partner_tokens_token_id_fkey FOREIGN KEY (token_id) REFERENCES public.token(id) ON DELETE CASCADE;


--
-- Name: pending_transaction pending_transaction_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pending_transaction
    ADD CONSTRAINT pending_transaction_token_id_fkey FOREIGN KEY (token_id) REFERENCES public.token(id);


--
-- Name: poll poll_creator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.poll
    ADD CONSTRAINT poll_creator_id_fkey FOREIGN KEY (creator_id) REFERENCES public."user"(id);


--
-- Name: poll_option poll_option_poll_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.poll_option
    ADD CONSTRAINT poll_option_poll_id_fkey FOREIGN KEY (poll_id) REFERENCES public.poll(id) ON DELETE CASCADE;


--
-- Name: poll poll_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.poll
    ADD CONSTRAINT poll_token_id_fkey FOREIGN KEY (token_id) REFERENCES public.token(id);


--
-- Name: poll_vote poll_vote_option_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.poll_vote
    ADD CONSTRAINT poll_vote_option_id_fkey FOREIGN KEY (option_id) REFERENCES public.poll_option(id) ON DELETE CASCADE;


--
-- Name: poll_vote poll_vote_poll_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.poll_vote
    ADD CONSTRAINT poll_vote_poll_id_fkey FOREIGN KEY (poll_id) REFERENCES public.poll(id);


--
-- Name: poll_vote poll_vote_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.poll_vote
    ADD CONSTRAINT poll_vote_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: position position_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."position"
    ADD CONSTRAINT position_token_id_fkey FOREIGN KEY (token_id) REFERENCES public.token(id);


--
-- Name: position position_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."position"
    ADD CONSTRAINT position_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: referral referral_referee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.referral
    ADD CONSTRAINT referral_referee_id_fkey FOREIGN KEY (referee_id) REFERENCES public."user"(id);


--
-- Name: referral referral_referrer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.referral
    ADD CONSTRAINT referral_referrer_id_fkey FOREIGN KEY (referrer_id) REFERENCES public."user"(id);


--
-- Name: reserve_distribution reserve_distribution_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reserve_distribution
    ADD CONSTRAINT reserve_distribution_token_id_fkey FOREIGN KEY (token_id) REFERENCES public.token(id);


--
-- Name: token_accolade token_accolade_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_accolade
    ADD CONSTRAINT token_accolade_token_id_fkey FOREIGN KEY (token_id) REFERENCES public.token(id);


--
-- Name: token token_creator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token
    ADD CONSTRAINT token_creator_id_fkey FOREIGN KEY (creator_id) REFERENCES public."user"(id);


--
-- Name: token_engagement token_engagement_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_engagement
    ADD CONSTRAINT token_engagement_token_id_fkey FOREIGN KEY (token_id) REFERENCES public.token(id);


--
-- Name: token_engagement token_engagement_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_engagement
    ADD CONSTRAINT token_engagement_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: token_leaderboard token_leaderboard_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_leaderboard
    ADD CONSTRAINT token_leaderboard_token_id_fkey FOREIGN KEY (token_id) REFERENCES public.token(id);


--
-- Name: token_leaderboard token_leaderboard_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_leaderboard
    ADD CONSTRAINT token_leaderboard_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: token_settings token_settings_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_settings
    ADD CONSTRAINT token_settings_token_id_fkey FOREIGN KEY (token_id) REFERENCES public.token(id);


--
-- Name: trade_event trade_event_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trade_event
    ADD CONSTRAINT trade_event_token_id_fkey FOREIGN KEY (token_id) REFERENCES public.token(id);


--
-- Name: trade trade_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trade
    ADD CONSTRAINT trade_token_id_fkey FOREIGN KEY (token_id) REFERENCES public.token(id);


--
-- Name: trade trade_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trade
    ADD CONSTRAINT trade_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: transfer_request transfer_request_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_request
    ADD CONSTRAINT transfer_request_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public."user"(id);


--
-- Name: transfer_request transfer_request_requester_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_request
    ADD CONSTRAINT transfer_request_requester_id_fkey FOREIGN KEY (requester_id) REFERENCES public."user"(id);


--
-- Name: user_achievement user_achievement_achievement_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_achievement
    ADD CONSTRAINT user_achievement_achievement_id_fkey FOREIGN KEY (achievement_id) REFERENCES public.achievement(id);


--
-- Name: user_achievement user_achievement_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_achievement
    ADD CONSTRAINT user_achievement_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: user user_claimed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_claimed_by_fkey FOREIGN KEY (claimed_by) REFERENCES public."user"(id);


--
-- Name: user_profile user_profile_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profile
    ADD CONSTRAINT user_profile_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: user_token_accolade user_token_accolade_accolade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_token_accolade
    ADD CONSTRAINT user_token_accolade_accolade_id_fkey FOREIGN KEY (accolade_id) REFERENCES public.token_accolade(id);


--
-- Name: user_token_accolade user_token_accolade_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_token_accolade
    ADD CONSTRAINT user_token_accolade_token_id_fkey FOREIGN KEY (token_id) REFERENCES public.token(id);


--
-- Name: user_token_accolade user_token_accolade_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_token_accolade
    ADD CONSTRAINT user_token_accolade_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: wallet_verification_challenge wallet_verification_challenge_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wallet_verification_challenge
    ADD CONSTRAINT wallet_verification_challenge_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- PostgreSQL database dump complete
--


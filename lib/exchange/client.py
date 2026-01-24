import ccxt
import os
import time
from typing import Dict, Optional
from lib.utils.logger import setup_logger

logger = setup_logger("exchange_client")

class TradingClient:
    """
    Handles interaction with the exchange (Bybit) for Pairs Trading.
    """
    
    def __init__(self, exchange_id: str = 'bybit', demo: bool = False):
        """
        Initializes the exchange connection.
        Keys must be set in environment variables:
        - EXCHANGE_API_KEY
        - EXCHANGE_SECRET_KEY
        """
        self.exchange_id = exchange_id
        
        api_key = os.environ.get("EXCHANGE_API_KEY")
        secret = os.environ.get("EXCHANGE_SECRET_KEY")
        
        if not api_key or not secret:
            logger.warning("API Keys not found in environment variables. Client will be Read-Only (Public Data).")
        
        exchange_class = getattr(ccxt, exchange_id)
        
        self.exchange = exchange_class({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'linear'  # Bybit Futures (USDT Perpetual)
            }
        })
        
        if demo:
            self.exchange.set_sandbox_mode(True)
            logger.info("⚠️ RUNNING IN DEMO/SANDBOX MODE ⚠️")

    def get_balance(self) -> float:
        """Returns available USDT balance."""
        try:
            balance = self.exchange.fetch_balance()
            # Usually 'USDT' free balance
            return balance.get('USDT', {}).get('free', 0.0)
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return 0.0

    def get_market_price(self, symbol: str) -> float:
        """Fetches current market price."""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return 0.0

    def calculate_qty(self, symbol: str, usdt_amount: float, price: float) -> float:
        """
        Calculates the correct quantity respecting exchange precision steps.
        """
        try:
            # Check market minimums (Min Notional, Min Qty)
            market = self.exchange.market(symbol)
            min_cost = market['limits']['cost']['min']
            
            if usdt_amount < min_cost:
                logger.warning(f"Order amount ${usdt_amount:.2f} is below min cost ${min_cost} for {symbol}.")
                return 0.0
                
            raw_qty = usdt_amount / price
            return self.exchange.amount_to_precision(symbol, raw_qty)
            
        except Exception as e:
            logger.error(f"Error calculating quantity for {symbol}: {e}")
            return 0.0

    def execute_pair_trade(self, 
                           symbol_a: str, side_a: str, 
                           symbol_b: str, side_b: str, 
                           usdt_per_leg: float) -> bool:
        """
        Executes a Pairs Trade (Leg A + Leg B).
        
        Args:
            symbol_a: Symbol for Leg A (e.g. 'BTC/USDT:USDT')
            side_a: 'buy' or 'sell'
            symbol_b: Symbol for Leg B
            side_b: 'buy' or 'sell'
            usdt_per_leg: Dollar amount to trade for EACH leg.
            
        Returns:
            bool: True if both orders submitted successfully.
        """
        logger.info(f"🚀 EXECUTING PAIR: {side_a.upper()} {symbol_a} | {side_b.upper()} {symbol_b} (${usdt_per_leg} each)")
        
        # 1. Fetch Prices
        price_a = self.get_market_price(symbol_a)
        price_b = self.get_market_price(symbol_b)
        
        if price_a == 0 or price_b == 0:
            logger.error("Could not fetch prices. Aborting.")
            return False
            
        # 2. Calculate Quantities
        qty_a = self.calculate_qty(symbol_a, usdt_per_leg, price_a)
        qty_b = self.calculate_qty(symbol_b, usdt_per_leg, price_b)
        
        if qty_a == 0 or qty_b == 0:
            logger.error("Quantity calculation failed (too small?). Aborting.")
            return False
            
        # 3. Execute Leg A
        try:
            order_a = self.exchange.create_order(symbol_a, 'market', side_a, qty_a)
            logger.info(f"✅ Leg A Filled: {side_a} {qty_a} {symbol_a} @ ~{price_a}")
        except Exception as e:
            logger.error(f"❌ Failed Leg A ({symbol_a}): {e}")
            return False
            
        # 4. Execute Leg B (Only if A succeeded to avoid unhedged exposure)
        # Note: In high freq, we might fire both async. For manual/low freq, sequential is safer 
        # to ensure we don't open Leg B if Leg A failed (api error, insufficient funds).
        try:
            order_b = self.exchange.create_order(symbol_b, 'market', side_b, qty_b)
            logger.info(f"✅ Leg B Filled: {side_b} {qty_b} {symbol_b} @ ~{price_b}")
            return True
        except Exception as e:
            logger.critical(f"❌ CRITICAL: Failed Leg B ({symbol_b}) after Leg A filled! You are unhedged! Error: {e}")
            # Optional: Emergency close Leg A here? 
            # For now, we just scream at the user.
            return False


import asyncio
from typing import List
from ready_trader_go import BaseAutoTrader, Instrument, Side, Lifespan

class MovingAverageTrader(BaseAutoTrader):
    """Auto-trader that uses a simple moving average crossover to generate buy and sell signals."""

    def __init__(self, loop: asyncio.AbstractEventLoop, team_name: str, secret: str):
        super().__init__(loop, team_name, secret)
        self.short_ma = 50  # Short-term moving average period
        self.long_ma = 200  # Long-term moving average period
        self.order_ids = itertools.count(1)
        self.bids = set()
        self.asks = set()
        self.position = 0

    def on_order_filled_message(self, client_order_id: int, price: int, volume: int) -> None:
        """Called when one of your orders is filled, partially or fully."""
        if client_order_id in self.bids:
            self.position += volume
        elif client_order_id in self.asks:
            self.position -= volume

    def on_order_status_message(self, client_order_id: int, fill_volume: int, remaining_volume: int, fees: int) -> None:
        """Called when the status of one of your orders changes."""
        if remaining_volume == 0:
            if client_order_id in self.bids:
                self.bids.discard(client_order_id)
            elif client_order_id in self.asks:
                self.asks.discard(client_order_id)

    def on_order_book_update_message(self, instrument: int, sequence_number: int, ask_prices: List[int],
                                     ask_volumes: List[int], bid_prices: List[int], bid_volumes: List[int]) -> None:
        """Called periodically to report the status of an order book."""
        if instrument == Instrument.FUTURE:
            # Calculate the short-term and long-term moving averages
            short_term_ma = sum(bid_volumes[i] for i in range(self.short_ma)) / self.short_ma
            long_term_ma = sum(bid_volumes[i] for i in range(self.long_ma)) / self.long_ma

            # If the short-term moving average crosses above the long-term moving average, generate a buy signal
            if short_term_ma > long_term_ma and self.position <= 0:
                bid_price = bid_prices[0]
                self.send_insert_order(next(self.order_ids), Side.BUY, bid_price, 10, Lifespan.GOOD_FOR_DAY)
                self.bids.add(client_order_id)

            # If the short-term moving average crosses below the long-term moving average, generate a sell signal
            elif short_term_ma < long_term_ma and self.position >= 0:
                ask_price = ask_prices[0]
                self.send_insert_order(next(self.order_ids), Side.SELL, ask_price, 10, Lifespan.GOOD_FOR_DAY)
                self.asks.add(client_order_id)

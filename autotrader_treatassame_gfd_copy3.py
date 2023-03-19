# Copyright 2021 Optiver Asia Pacific Pty. Ltd.
#
# This file is part of Ready Trader Go.
#
#     Ready Trader Go is free software: you can redistribute it and/or
#     modify it under the terms of the GNU Affero General Public License
#     as published by the Free Software Foundation, either version 3 of
#     the License, or (at your option) any later version.
#
#     Ready Trader Go is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU Affero General Public License for more details.
#
#     You should have received a copy of the GNU Affero General Public
#     License along with Ready Trader Go.  If not, see
#     <https://www.gnu.org/licenses/>.
import asyncio
import itertools
import time
import random
from typing import List
from collections import deque

from ready_trader_go import BaseAutoTrader, Instrument, Lifespan, MAXIMUM_ASK, MINIMUM_BID, Side

INTERVAL = 1
LOT_SIZE = 10
POSITION_LIMIT = 100
TICK_SIZE_IN_CENTS = 100
MIN_BID_NEAREST_TICK = (MINIMUM_BID + TICK_SIZE_IN_CENTS) // TICK_SIZE_IN_CENTS * TICK_SIZE_IN_CENTS
MAX_ASK_NEAREST_TICK = MAXIMUM_ASK // TICK_SIZE_IN_CENTS * TICK_SIZE_IN_CENTS
RANDOM_SIZE = 5

class AutoTrader(BaseAutoTrader):
    """Example Auto-trader.

    When it starts this auto-trader places ten-lot bid and ask orders at the
    current best-bid and best-ask prices respectively. Thereafter, if it has
    a long position (it has bought more lots than it has sold) it reduces its
    bid and ask prices. Conversely, if it has a short position (it has sold
    more lots than it has bought) then it increases its bid and ask prices.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, team_name: str, secret: str):
        """Initialise a new instance of the AutoTrader class."""
        super().__init__(loop, team_name, secret)
        self.order_ids = itertools.count(1)
        self.bids = set()
        self.asks = set()
        self.ask_id = self.ask_price = self.bid_id = self.bid_price = self.position = 0
        self.last_etf_price = [0,0]
        self.last_future_price = [0,0]
        self.last_etf_volume = [0,0]
        self.last_future_volume = [0,0]
        self.last_sequence_number = 0
        self.timestamps = deque()
        self.etf_orders = set()
        self.new_bid_price = 0
        self.new_ask_price = 0
        self.active_orders = deque()
        self.order_volumes = [0]*4000

    def on_error_message(self, client_order_id: int, error_message: bytes) -> None:
        """Called when the exchange detects an error.

        If the error pertains to a particular order, then the client_order_id
        will identify that order, otherwise the client_order_id will be zero.
        """
        self.logger.warning("error with order %d: %s", client_order_id, error_message.decode())
        if client_order_id != 0 and (client_order_id in self.bids or client_order_id in self.asks):
            self.on_order_status_message(client_order_id, 0, 0, 0)

    def on_hedge_filled_message(self, client_order_id: int, price: int, volume: int) -> None:
        """Called when one of your hedge orders is filled.
        The price is the average price at which the order was (partially) filled,
        which may be better than the order's limit price. The volume is
        the number of lots filled at that price.
        """

        self.logger.info("received hedge filled for order %d with average price %d and volume %d", client_order_id,
                         price, volume)

    def on_order_book_update_message(self, instrument: int, sequence_number: int, ask_prices: List[int],
                                     ask_volumes: List[int], bid_prices: List[int], bid_volumes: List[int]) -> None:
        """Called periodically to report the status of an order book.

        The sequence number can be used to detect missed or out-of-order
        messages. The five best available ask (i.e. sell) and bid (i.e. buy)
        prices are reported along with the volume available at each of those
        price levels.
        """
        # remove older timestamps
        self.remove_old_timestamps()
        # remove active orders
        self.remove_old_orders()
        print(str(self.active_orders))
        print("position: "+str(self.position))
        self.logger.info("received order book for instrument %s with sequence number %d", "future" if instrument==0 else "etf",
                         sequence_number)
        # price_adjustment = - (self.position // LOT_SIZE) * TICK_SIZE_IN_CENTS #+ random.randint(-RANDOM_SIZE,RANDOM_SIZE)*TICK_SIZE_IN_CENTS
        # # price_adjustment = 0
        # self.new_bid_price = max(bid_prices) + price_adjustment if max(bid_prices) != 0 else 0
        # self.new_ask_price = min(ask_prices) + price_adjustment if min(ask_prices) != 0 else 0

        if instrument == Instrument.FUTURE:
            # price_adjustment = - (self.position // LOT_SIZE) * TICK_SIZE_IN_CENTS #+ random.randint(-RANDOM_SIZE,RANDOM_SIZE)*TICK_SIZE_IN_CENTS
            # # price_adjustment = 0
            # self.new_bid_price = max(bid_prices) + price_adjustment if max(bid_prices) != 0 else 0
            # self.new_ask_price = min(ask_prices) + price_adjustment if min(ask_prices) != 0 else 0
            self.last_future_price[0]=max(bid_prices)
            self.last_future_price[1]=min(ask_prices)
            self.last_future_volume[0]=bid_volumes[bid_prices.index(max(bid_prices))]
            self.last_future_volume[1]=ask_volumes[ask_prices.index(min(ask_prices))]
            # self.logger.info("futures: " + str(ask_prices))
            if(self.last_etf_price[0]!=0):
                # print("got in future")
                # if self.bid_id != 0 and new_bid_price not in (self.bid_price, 0):
                #     self.send_cancel_order(self.bid_id)
                #     self.logger.info("canceled bid order with bid id:"+str(self.bid_id))
                #     self.bid_id = 0
                #     self.timestamps.append(time.time())
                # if self.ask_id != 0 and new_ask_price not in (self.ask_price, 0):
                #     self.send_cancel_order(self.ask_id)
                #     self.logger.info("canceled ask order with ask id:"+str(self.ask_id))
                #     self.ask_id = 0
                #     self.timestamps.append(time.time())

                self.remove_old_timestamps()
                # Buy ETF sell Future when min(ask prices) of ETF < max(bid price) of future
                # if self.bid_id == 0 and new_bid_price != 0 and self.position < POSITION_LIMIT and self.last_etf_price[1]<self.last_future_price[0]:
                if self.new_bid_price != 0 and self.position < POSITION_LIMIT and self.last_etf_price[1]<self.last_future_price[0]:
                    times = self.clamp(self.last_etf_volume[1]//LOT_SIZE,0,min((POSITION_LIMIT-self.position)//(2*LOT_SIZE),50-len(self.timestamps)))
                    # times = min((POSITION_LIMIT-self.position)//(2*LOT_SIZE),50-len(self.timestamps))
                    #  -100<position<100
                    #  每秒50个operation以内
                    # times = self.clamp(self.last_etf_volume[1]//LOT_SIZE,0,3)
                    # times = max(times,1)
                    # for i in range(times):
                        # if self.position+10>=POSITION_LIMIT:
                        #     break
                    if times>=1:
                        self.bid_id = next(self.order_ids)
                        self.bid_price = self.new_bid_price
                        # self.bid_price = self.last_etf_price[0]
                        self.send_insert_order(self.bid_id, Side.BUY, self.bid_price, int(LOT_SIZE*times), Lifespan.GOOD_FOR_DAY)
                        self.timestamps.append(time.time())
                        self.bids.add(self.bid_id)
                        self.active_orders.append(self.bid_id)
                        self.order_volumes[self.bid_id]=int(LOT_SIZE*times)
                        print(f"Buy {int(LOT_SIZE*times)}")
                # Sell ETF buy Future when max(bid price) of ETF > min(ask price) of future
                # if self.ask_id == 0 and new_ask_price != 0 and self.position > -POSITION_LIMIT and self.last_etf_price[0]>self.last_future_price[1]:
                if self.new_ask_price != 0 and self.position > -POSITION_LIMIT and self.last_etf_price[0]>self.last_future_price[1]:
                    times = self.clamp(self.last_etf_volume[0]//LOT_SIZE,0,min((self.position + POSITION_LIMIT)//(2*LOT_SIZE),50-len(self.timestamps)))
                    # times = min((self.position + POSITION_LIMIT)//(2*LOT_SIZE),50-len(self.timestamps))
                    # times = self.clamp(self.last_etf_volume[0]//LOT_SIZE,0,3)
                    # times = max(times,1)
                    # self.logger.info(f"sell ETF with {LOT_SIZE} per lot for {times} times, now I have {self.position} ETFs")
                    # # print(f"sell ETF with 10 per lot for {times} times, now I have {self.position} ETFs")
                    # for i in range(times):
                        # if self.position-10>=POSITION_LIMIT:
                        #     break
                    if times>=1:
                        self.ask_id = next(self.order_ids)
                        self.ask_price = self.new_ask_price
                        # self.ask_price = self.last_etf_price[1]
                        self.send_insert_order(self.ask_id, Side.SELL, self.ask_price, int(LOT_SIZE*times), Lifespan.GOOD_FOR_DAY)
                        self.timestamps.append(time.time())
                        self.asks.add(self.ask_id)
                        self.active_orders.append(self.ask_id)
                        self.order_volumes[self.ask_id]=-int(LOT_SIZE*times)
                        print(f"Sell {int(LOT_SIZE*times)}")

        if instrument == Instrument.ETF:
            self.last_etf_price[0]=max(bid_prices) 
            self.last_etf_price[1]=min(ask_prices)
            self.last_etf_volume[0]=bid_volumes[bid_prices.index(max(bid_prices))]
            self.last_etf_volume[1]=ask_volumes[ask_prices.index(min(ask_prices))]
            #price_adjustment = - (self.position // LOT_SIZE) * TICK_SIZE_IN_CENTS #+ random.randint(-RANDOM_SIZE,RANDOM_SIZE)*TICK_SIZE_IN_CENTS
            price_adjustment = 0
            # self.new_ask_price = max(bid_prices) + price_adjustment if max(bid_prices) != 0 else 0
            # self.new_bid_price = min(ask_prices) + price_adjustment if min(ask_prices) != 0 else 0
            self.new_ask_price = max(bid_prices) + price_adjustment - 3*TICK_SIZE_IN_CENTS if max(bid_prices) != 0 else 0
            self.new_bid_price = min(ask_prices) + price_adjustment + 3*TICK_SIZE_IN_CENTS if min(ask_prices) != 0 else 0
            if(self.last_future_price[0]!=0):
                # print("got in etf")
                # if self.bid_id != 0 and new_bid_price not in (self.bid_price, 0):
                #     self.send_cancel_order(self.bid_id)
                #     self.logger.info("canceled bid order with bid id:"+str(self.bid_id))
                #     self.bid_id = 0
                #     self.timestamps.append(time.time())
                # if self.ask_id != 0 and new_ask_price not in (self.ask_price, 0):
                #     self.send_cancel_order(self.ask_id)
                #     self.logger.info("canceled ask order with ask id:"+str(self.ask_id))
                #     self.ask_id = 0
                #     self.timestamps.append(time.time())

                self.remove_old_timestamps()

                # Buy ETF sell Future when min(ask prices) of ETF < max(bid price) of future
                # if self.bid_id == 0 and new_bid_price != 0 and self.position < POSITION_LIMIT and self.last_etf_price[1]<self.last_future_price[0]:
                if self.new_bid_price != 0 and self.position < POSITION_LIMIT and self.last_etf_price[1]<self.last_future_price[0]:
                    times = self.clamp(self.last_etf_volume[1]//LOT_SIZE,0,min((POSITION_LIMIT-self.position)//(2*LOT_SIZE),50-len(self.timestamps)))
                    # times = min((POSITION_LIMIT-self.position)//(2*LOT_SIZE),50-len(self.timestamps))
                    if times>=1:
                    # times = self.clamp(self.last_etf_volume[1]//LOT_SIZE,0,3)
                    # times = max(times,1)
                    # self.logger.info(f"buy ETF with {LOT_SIZE} per lot for {times} times, now I have {self.position} ETFs")
                    # for i in range(times):
                        # if self.position+10>=POSITION_LIMIT:
                        #     break
                        self.bid_id = next(self.order_ids)
                        self.bid_price = self.new_bid_price
                        # self.bid_price = self.last_etf_price[0]
                        self.send_insert_order(self.bid_id, Side.BUY, self.bid_price, int(LOT_SIZE*times), Lifespan.GOOD_FOR_DAY)
                        self.timestamps.append(time.time())
                        self.bids.add(self.bid_id)
                        self.etf_orders.add(self.bid_id)
                        self.active_orders.append(self.bid_id)
                        self.order_volumes[self.bid_id]=int(LOT_SIZE*times)
                        print(f"Buy {int(LOT_SIZE*times)}")
                        # self.position-=LOT_SIZE
                # Sell ETF buy Future when max(bid price) of ETF > min(ask price) of future
                # if self.ask_id == 0 and new_ask_price != 0 and self.position > -POSITION_LIMIT and self.last_etf_price[0]>self.last_future_price[1]:
                if self.new_ask_price != 0 and self.position > -POSITION_LIMIT and self.last_etf_price[0]>self.last_future_price[1]:
                    times = self.clamp(self.last_etf_volume[0]//LOT_SIZE,0,min((self.position + POSITION_LIMIT)//(2*LOT_SIZE),50-len(self.timestamps)))
                    # times = min((self.position + POSITION_LIMIT)//(2*LOT_SIZE),50-len(self.timestamps))
                    # times = max(times,1)
                    # times = self.clamp(self.last_etf_volume[0]//LOT_SIZE,0,3)
                    # times = max(times,1)
                    # self.logger.info(f"sell ETF with 10 per lot for {times} times, now I have {self.position} ETFs")
                    # # print(f"sell ETF with 10 per lot for {times} times, now I have {self.position} ETFs")
                    # for i in range(times):
                        # if self.position-10<=-POSITION_LIMIT:
                        #     break
                    if times>=1:
                        self.ask_id = next(self.order_ids)
                        self.ask_price = self.new_ask_price
                        # self.ask_price = self.last_etf_price[1]
                        self.send_insert_order(self.ask_id, Side.SELL, self.ask_price, int(LOT_SIZE*times), Lifespan.GOOD_FOR_DAY)
                        self.timestamps.append(time.time())
                        self.asks.add(self.ask_id)
                        self.etf_orders.add(self.ask_id)
                        self.active_orders.append(self.ask_id)
                        self.order_volumes[self.ask_id]=-int(LOT_SIZE*times)
                        print(f"Sell {int(LOT_SIZE*times)}")
                        # self.position+=LOT_SIZE
        # self.last_sequence_number=sequence_number
        self.remove_old_orders()

    def mean(lis):
        return sum(lis)/len(lis)
    
    def clamp(self,n, smallest, largest):
        return max(smallest, min(n, largest))

    def remove_old_timestamps(self):
        now = time.time()
        while self.timestamps and self.timestamps[0]<now - INTERVAL:
            self.timestamps.popleft()
    def remove_old_orders(self):
        num = len(self.active_orders)-8
        if num>0:
            for i in range(num):
                removed_order = self.active_orders.popleft()
                self.send_cancel_order(removed_order)
                self.timestamps.append(time.time())
        active_amounts_buy = 0
        active_amounts_sell = 0
        for order_ids in self.active_orders:
            if self.order_volumes[order_ids]>0:
                active_amounts_buy += self.order_volumes[order_ids]
            else:
                active_amounts_sell += self.order_volumes[order_ids]
        countid = 0
        tobe_deleted = []
        for order_ids in self.active_orders:
            if active_amounts_buy + self.position > 100 and self.order_volumes[order_ids]>0:
                tobe_deleted.append(order_ids)
                active_amounts_buy -= self.order_volumes[order_ids]
                self.send_cancel_order(order_ids)
            if active_amounts_sell + self.position < -100 and self.order_volumes[order_ids]<0:
                tobe_deleted.append(order_ids)
                active_amounts_sell -= self.order_volumes[order_ids]
                self.send_cancel_order(order_ids)
        for delete_ids in tobe_deleted:
            self.active_orders.remove(delete_ids)

        

    def on_order_filled_message(self, client_order_id: int, price: int, volume: int) -> None:
        """Called when one of your orders is filled, partially or fully.

        The price is the price at which the order was (partially) filled,
        which may be better than the order's limit price. The volume is
        the number of lots filled at that price.
        """
        self.logger.info("received order filled for order %d with price %d and volume %d", client_order_id,
                         price, volume)
        if client_order_id in self.bids:
            self.position += volume
            self.send_hedge_order(next(self.order_ids), Side.ASK, MIN_BID_NEAREST_TICK, volume) #limit 
            self.timestamps.append(time.time())
            # self.send_hedge_order(next(self.order_ids), Side.ASK, self.future_prices[client_order_id], volume)
        elif client_order_id in self.asks:
            self.position -= volume
            self.send_hedge_order(next(self.order_ids), Side.BID, MAX_ASK_NEAREST_TICK, volume)
            self.timestamps.append(time.time())
            # self.send_hedge_order(next(self.order_ids), Side.ASK, self.future_prices[client_order_id], volume)

    def on_order_status_message(self, client_order_id: int, fill_volume: int, remaining_volume: int,
                                fees: int) -> None:
        """Called when the status of one of your orders changes.

        The fill_volume is the number of lots already traded, remaining_volume
        is the number of lots yet to be traded and fees is the total fees for
        this order. Remember that you pay fees for being a market taker, but
        you receive fees for being a market maker, so fees can be negative.

        If an order is cancelled its remaining volume will be zero.
        """
        self.logger.info("received order status for %s order %d with fill volume %d remaining %d and fees %d","bid" if client_order_id in self.bids else "ask",
                         client_order_id, fill_volume, remaining_volume, fees)

        if fill_volume!=0:
            print("etf" if client_order_id in self.etf_orders else "future")
        if remaining_volume == 0:
            if(client_order_id in self.active_orders):
                self.active_orders.remove(client_order_id)
            if client_order_id == self.bid_id:
                self.bid_id = 0
            elif client_order_id == self.ask_id:
                self.ask_id = 0
            if fill_volume == 0:
                self.timestamps.append(time.time())
                # print("etf" if client_order_id in self.etf_orders else "future")
            # It could be either a bid or an ask
            self.bids.discard(client_order_id)
            self.asks.discard(client_order_id)

    def on_trade_ticks_message(self, instrument: int, sequence_number: int, ask_prices: List[int],
                               ask_volumes: List[int], bid_prices: List[int], bid_volumes: List[int]) -> None:
        """Called periodically when there is trading activity on the market.

        The five best ask (i.e. sell) and bid (i.e. buy) prices at which there
        has been trading activity are reported along with the aggregated volume
        traded at each of those price levels.

        If there are less than five prices on a side, then zeros will appear at
        the end of both the prices and volumes arrays.
        """
        self.logger.info("received trade ticks for instrument %d with sequence number %d", instrument,
                         sequence_number)
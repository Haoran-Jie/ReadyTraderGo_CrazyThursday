// Copyright 2021 Optiver Asia Pacific Pty. Ltd.
//
// This file is part of Ready Trader Go.
//
//     Ready Trader Go is free software: you can redistribute it and/or
//     modify it under the terms of the GNU Affero General Public License
//     as published by the Free Software Foundation, either version 3 of
//     the License, or (at your option) any later version.
//
//     Ready Trader Go is distributed in the hope that it will be useful,
//     but WITHOUT ANY WARRANTY; without even the implied warranty of
//     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//     GNU Affero General Public License for more details.
//
//     You should have received a copy of the GNU Affero General Public
//     License along with Ready Trader Go.  If not, see
//     <https://www.gnu.org/licenses/>.
#include <array>

#include <boost/asio/io_context.hpp>

#include <ready_trader_go/logging.h>

#include "autotrader.h"

using namespace ReadyTraderGo;

RTG_INLINE_GLOBAL_LOGGER_WITH_CHANNEL(LG_AT, "AUTO")

constexpr int LOT_SIZE = 10;
constexpr int POSITION_LIMIT = 100;
constexpr int TICK_SIZE_IN_CENTS = 100;
constexpr int MIN_BID_NEARST_TICK = (MINIMUM_BID + TICK_SIZE_IN_CENTS) / TICK_SIZE_IN_CENTS * TICK_SIZE_IN_CENTS;
constexpr int MAX_ASK_NEAREST_TICK = MAXIMUM_ASK / TICK_SIZE_IN_CENTS * TICK_SIZE_IN_CENTS;

AutoTrader::AutoTrader(boost::asio::io_context& context) : BaseAutoTrader(context)
{
    // for(int i=0;i<4000;i++){
    //     price_etf_ask[i][0]=-1;
    //     price_etf_bid[i][0]=-1;
    //     price_future_ask[i][0]=-1;
    //     price_future_bid[i][0]=-1;
    // }
   
   
}

void AutoTrader::DisconnectHandler()
{
    BaseAutoTrader::DisconnectHandler();
    RLOG(LG_AT, LogLevel::LL_INFO) << "execution connection lost";
}

void AutoTrader::ErrorMessageHandler(unsigned long clientOrderId,
                                     const std::string& errorMessage)
{
    RLOG(LG_AT, LogLevel::LL_INFO) << "error with order " << clientOrderId << ": " << errorMessage;
    if (clientOrderId != 0 && ((mAsks.count(clientOrderId) == 1) || (mBids.count(clientOrderId) == 1)))
    {
        OrderStatusMessageHandler(clientOrderId, 0, 0, 0);
    }
}

void AutoTrader::HedgeFilledMessageHandler(unsigned long clientOrderId,
                                           unsigned long price,
                                           unsigned long volume)
{
    RLOG(LG_AT, LogLevel::LL_INFO) << "hedge order " << clientOrderId << " filled for " << volume
                                   << " lots at $" << price << " average price in cents";
}

void AutoTrader::OrderBookMessageHandler(Instrument instrument,
                                         unsigned long sequenceNumber,
                                         const std::array<unsigned long, TOP_LEVEL_COUNT>& askPrices,
                                         const std::array<unsigned long, TOP_LEVEL_COUNT>& askVolumes,
                                         const std::array<unsigned long, TOP_LEVEL_COUNT>& bidPrices,
                                         const std::array<unsigned long, TOP_LEVEL_COUNT>& bidVolumes)
{
    RLOG(LG_AT, LogLevel::LL_INFO) << "order book received for " << instrument << " instrument (future is 0 else etf)"
                                   << ": ask prices: " << askPrices[0]
                                   << "; ask volumes: " << askVolumes[0]
                                   << "; bid prices: " << bidPrices[0]
                                   << "; bid volumes: " << bidVolumes[0];
    unsigned long priceAdjustment = - (mPosition / LOT_SIZE) * TICK_SIZE_IN_CENTS;
    unsigned long min_ask_Prices_temp = *std::min_element(askPrices.begin(), askPrices.end());
    unsigned long max_bid_Prices_temp = *std::max_element(bidPrices.begin(), bidPrices.end());
    unsigned long newAskPrice = (min_ask_Prices_temp != 0) ? min_ask_Prices_temp + priceAdjustment : 0;
    unsigned long newBidPrice = (max_bid_Prices_temp != 0) ? max_bid_Prices_temp + priceAdjustment : 0;
    RLOG(LG_AT, LogLevel::LL_INFO) <<newBidPrice <<"Debug:max_ask_Prices_temp " << max_bid_Prices_temp;
    
    if (instrument == Instrument::FUTURE)
    {
        price_future_ask=askPrices;
        price_future_bid=bidPrices;
        update_future[sequenceNumber]=true;
        future_last=sequenceNumber;
        RLOG(LG_AT, LogLevel::LL_INFO)<< sequenceNumber<<update_future[sequenceNumber]<<update_etf[sequenceNumber] ;
        if(etf_last!=-1){ // not empty
            RLOG(LG_AT, LogLevel::LL_INFO) << "1-2";
            if (mAskId != 0 && newAskPrice != 0 && newAskPrice != mAskPrice)
            {
                SendCancelOrder(mAskId);
                mAskId = 0;
            }
            if (mBidId != 0 && newBidPrice != 0 && newBidPrice != mBidPrice)
            {
                SendCancelOrder(mBidId);
                mBidId = 0;
            }
            unsigned long min_etf_ask=*std::min_element(price_etf_ask.begin(),price_etf_ask.end());
            unsigned long max_future_bid=*std::max_element(price_future_bid.begin(),price_future_bid.end());
            // for (int j = 0; j < price_etf_ask.size(); j++ )
            // {   
            //     RLOG(LG_AT, LogLevel::LL_INFO) << "Debug: price_etf_ask "<<j<<" "<<price_etf_ask[future_last][j];
            // }
          
            RLOG(LG_AT, LogLevel::LL_INFO) << "Debug: min_etf_ask  "<<min_etf_ask;
            // Buy ETF sell Future when min(ask prices) of ETF < max(bid price) of future
            if (mBidId == 0 && newBidPrice != 0 && mPosition < POSITION_LIMIT && min_etf_ask<max_future_bid)        
            {
                mBidId = mNextMessageId++;
                mBidPrice = newBidPrice;
                SendInsertOrder(mBidId, Side::BUY, newBidPrice, LOT_SIZE, Lifespan::FILL_AND_KILL);
                mBids.emplace(mBidId);
                RLOG(LG_AT, LogLevel::LL_INFO) << "send1 ";
            }
            unsigned long min_future_ask= *std::min_element(price_future_ask.begin(),price_future_ask.end());
            unsigned long max_etf_bid=*std::max_element(price_etf_bid.begin(),price_etf_bid.end());
            if (mAskId == 0 && newAskPrice != 0 && mPosition > -POSITION_LIMIT && min_future_ask <max_etf_bid)
            {
                mAskId = mNextMessageId++;
                mAskPrice = newAskPrice;
                SendInsertOrder(mAskId, Side::SELL, newAskPrice, LOT_SIZE, Lifespan::FILL_AND_KILL);
                mAsks.emplace(mAskId);
                RLOG(LG_AT, LogLevel::LL_INFO) << "send2 ";
            }
        }
        
    }
    if (instrument == Instrument::ETF)
    {
        // std::copy_n(askPrices.begin(), askPrices.size(), price_etf_ask[sequenceNumber].begin());
        // std::copy_n(bidPrices.begin(), bidPrices.size(), price_etf_bid[sequenceNumber].begin());
        price_etf_ask=askPrices;
        price_etf_bid=bidPrices;
        
        update_etf[sequenceNumber]=true;
        etf_last=sequenceNumber;
        // RLOG(LG_AT, LogLevel::LL_INFO)<< sequenceNumber<<update_future[sequenceNumber]<<update_etf[sequenceNumber] ;
        if(future_last!=-1){ // not empty
            if (mAskId != 0 && newAskPrice != 0 && newAskPrice != mAskPrice)
            {
                SendCancelOrder(mAskId);
                mAskId = 0;
            }
            if (mBidId != 0 && newBidPrice != 0 && newBidPrice != mBidPrice)
            {
                SendCancelOrder(mBidId);
                mBidId = 0;
            }
            unsigned long min_etf_ask=*std::min_element(price_etf_ask.begin(),price_etf_ask.end());
            unsigned long max_future_bid=*std::max_element(price_future_bid.begin(),price_future_bid.end());
            // Buy ETF sell Future when min(ask prices) of ETF < max(bid price) of future
            RLOG(LG_AT, LogLevel::LL_INFO)<<(mBidId == 0)<<(newBidPrice != 0)<<(mPosition < POSITION_LIMIT)<<(min_etf_ask<max_future_bid);
            if (mBidId == 0 && newBidPrice != 0 && mPosition < POSITION_LIMIT && min_etf_ask<max_future_bid)
            {
                mBidId = mNextMessageId++;
                mBidPrice = newBidPrice;
                SendInsertOrder(mBidId, Side::BUY, newBidPrice, LOT_SIZE, Lifespan::FILL_AND_KILL);
                mBids.emplace(mBidId);
                RLOG(LG_AT, LogLevel::LL_INFO)<<newBidPrice<< std::endl<<sequenceNumber;
                RLOG(LG_AT, LogLevel::LL_INFO) << "send3 ";
            }
            unsigned long min_future_ask= *std::min_element(price_future_ask.begin(),price_future_ask.end());
            unsigned long max_etf_bid=*std::max_element(price_etf_bid.begin(),price_etf_bid.end());
            // RLOG(LG_AT, LogLevel::LL_INFO)<<"Data:"<<sequenceNumber<<std::endl<<newBidPrice<<std::endl<<min_etf_ask<<std::endl<<max_future_bid<<std::endl<<min_future_ask<<std::endl<<max_etf_bid;
            if (mAskId == 0 && newAskPrice != 0 && mPosition > -POSITION_LIMIT && min_future_ask <max_etf_bid)
            {
                mAskId = mNextMessageId++;
                mAskPrice = newAskPrice;
                SendInsertOrder(mAskId, Side::SELL, newAskPrice, LOT_SIZE, Lifespan::FILL_AND_KILL);
                mAsks.emplace(mAskId);
                RLOG(LG_AT, LogLevel::LL_INFO) << "send4 ";
            }
        }
        
    }
}

void AutoTrader::OrderFilledMessageHandler(unsigned long clientOrderId,
                                           unsigned long price,
                                           unsigned long volume)
{
    RLOG(LG_AT, LogLevel::LL_INFO) << "order " << clientOrderId << " filled for " << volume
                                   << " lots at $" << price << " cents";
    if (mAsks.count(clientOrderId) == 1)
    {
        mPosition -= (long)volume;
        SendHedgeOrder(mNextMessageId++, Side::BUY, MAX_ASK_NEAREST_TICK, volume);
    }
    else if (mBids.count(clientOrderId) == 1)
    {
        mPosition += (long)volume;
        SendHedgeOrder(mNextMessageId++, Side::SELL, MIN_BID_NEARST_TICK, volume);
    }
}

void AutoTrader::OrderStatusMessageHandler(unsigned long clientOrderId,
                                           unsigned long fillVolume,
                                           unsigned long remainingVolume,
                                           signed long fees)
{
    if (remainingVolume == 0)
    {
        if (clientOrderId == mAskId)
        {
            mAskId = 0;
        }
        else if (clientOrderId == mBidId)
        {
            mBidId = 0;
        }

        mAsks.erase(clientOrderId);
        mBids.erase(clientOrderId);
    }
}

void AutoTrader::TradeTicksMessageHandler(Instrument instrument,
                                          unsigned long sequenceNumber,
                                          const std::array<unsigned long, TOP_LEVEL_COUNT>& askPrices,
                                          const std::array<unsigned long, TOP_LEVEL_COUNT>& askVolumes,
                                          const std::array<unsigned long, TOP_LEVEL_COUNT>& bidPrices,
                                          const std::array<unsigned long, TOP_LEVEL_COUNT>& bidVolumes)
{
    RLOG(LG_AT, LogLevel::LL_INFO) << "trade ticks received for " << instrument << " instrument"
                                   << ": ask prices: " << askPrices[0]
                                   << "; ask volumes: " << askVolumes[0]
                                   << "; bid prices: " << bidPrices[0]
                                   << "; bid volumes: " << bidVolumes[0];
}

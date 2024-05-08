#Team 12 - Tech Titans:


import datetime as dt 

import time 

import logging 

import numpy as np 

 

from optibook.synchronous_client import Exchange 

from optibook.common_types import InstrumentType, OptionKind 

 

from math import floor, ceil 

from black_scholes import call_value, put_value, call_delta, put_delta 

from libs import calculate_current_time_to_date 

 

exchange = Exchange() 

exchange.connect() 

 

logging.getLogger('client').setLevel('ERROR') 

 

instruments = exchange.get_instruments() 

constituents = {'NVDA': 908.06, 'ING': 129.24, 'SAN': 124.78, 'PFE': 2245.39, 'CSCO': 953.21} 

weights = np.array(list(constituents.values())) 

r = 0.03 

tick = 0.10 

volume = 50 

vol = 3.0 

stocks = ['NVDA', 'ING', 'SAN', 'PFE', 'CSCO'] 

index_futures = ['OB5X_202406_F', 'OB5X_202409_F', 'OB5X_202412_F'] 

index_options = ['OB5X_202406_080C', 'OB5X_202406_080P', 'OB5X_202406_100C', 'OB5X_202406_100P', 'OB5X_202406_120C', 'OB5X_202406_120P'] 

equity_futures = ['NVDA_202406_F', 'NVDA_202409_F', 'NVDA_202412_F'] 

all_used = ['OB5X_202406_F', 'OB5X_202409_F', 'OB5X_202412_F','OB5X_202406_080C', 'OB5X_202406_080P', 'OB5X_202406_100C', 'OB5X_202406_100P', 'OB5X_202406_120C', 'OB5X_202406_120P','NVDA_202406_F', 'NVDA_202409_F', 'NVDA_202412_F'] 

 

def round_down_to_tick(price, tick_size): 

    return floor(price / tick_size) * tick_size 

 

def round_up_to_tick(price, tick_size): 

    return ceil(price / tick_size) * tick_size 

 

def get_midpoint_value(instrument_id): 

    order_book = exchange.get_last_price_book(instrument_id=instrument_id) 

 

    # If the instrument doesn't have prices at all or on either side, we cannot calculate a midpoint and return None 

    if not (order_book and order_book.bids and order_book.asks): 

        return None 

    else: 

        midpoint = (order_book.bids[0].price + order_book.asks[0].price) / 2.0 

        return midpoint 

 

def calculate_theoretical_option_value(expiry, strike, option_kind, stock_value, interest_rate, volatility): 

    time_to_expiry = calculate_current_time_to_date(expiry) 

 

    if option_kind == OptionKind.CALL: 

        option_value = call_value(S=stock_value, K=strike, T=time_to_expiry, r=interest_rate, sigma=volatility) 

    elif option_kind == OptionKind.PUT: 

        option_value = put_value(S=stock_value, K=strike, T=time_to_expiry, r=interest_rate, sigma=volatility) 

 

    return option_value 

 

def calculate_option_delta(expiry_date, strike, option_kind, stock_value, interest_rate, volatility): 

    time_to_expiry = calculate_current_time_to_date(expiry_date) 

 

    if option_kind == OptionKind.CALL: 

        option_delta = call_delta(S=stock_value, K=strike, T=time_to_expiry, r=interest_rate, sigma=volatility) 

    elif option_kind == OptionKind.PUT: 

        option_delta = put_delta(S=stock_value, K=strike, T=time_to_expiry, r=interest_rate, sigma=volatility) 

    else: 

        raise Exception(f"""Got unexpected value for option_kind argument, should be OptionKind.CALL or OptionKind.PUT but was {option_kind}.""") 

 

    return option_delta 

 

def update_quotes(option_id, theoretical_price, credit, volume, position_limit, tick_size): 

    # Print any new trades 

    trades = exchange.poll_new_trades(instrument_id=option_id) 

    for trade in trades: 

        print(f'- Last period, traded {trade.volume} lots in {option_id} at price {trade.price:.2f}, side {trade.side}.') 

 

    # Pull (remove) all existing outstanding orders 

    orders = exchange.get_outstanding_orders(instrument_id=option_id) 

    for order_id, order in orders.items(): 

        print(f'- Deleting old {order.side} order in {option_id} for {order.volume} @ {order.price:8.2f}.') 

        exchange.delete_order(instrument_id=option_id, order_id=order_id) 

 

    # Calculate bid and ask price 

    bid_price = round_down_to_tick(theoretical_price - credit, tick_size) 

    ask_price = round_up_to_tick(theoretical_price + credit, tick_size) 

 

    # Calculate bid and ask volumes, taking into account the provided position_limit 

    position = exchange.get_positions()[option_id] 

 

    max_volume_to_buy = position_limit - position 

    max_volume_to_sell = position_limit + position 

 

    bid_volume = min(volume, max_volume_to_buy) 

    ask_volume = min(volume, max_volume_to_sell) 

 

    # Insert new limit orders 

    if bid_volume > 0: 

        print(f'- Inserting bid limit order in {option_id} for {bid_volume} @ {bid_price:8.2f}.') 

        exchange.insert_order( 

            instrument_id=option_id, 

            price=bid_price, 

            volume=bid_volume, 

            side='bid', 

            order_type='limit', 

        ) 

    if ask_volume > 0: 

        print(f'- Inserting ask limit order in {option_id} for {ask_volume} @ {ask_price:8.2f}.') 

        exchange.insert_order( 

            instrument_id=option_id, 

            price=ask_price, 

            volume=ask_volume, 

            side='ask', 

            order_type='limit', 

        ) 

 
 

def load_instruments_for_underlying(underlying_stock_id): 

    all_instruments = exchange.get_instruments() 

    stock = all_instruments[underlying_stock_id] 

    options = {instrument_id: instrument 

               for instrument_id, instrument in all_instruments.items() 

               if instrument.instrument_type == InstrumentType.STOCK_OPTION 

               and instrument.base_instrument_id == underlying_stock_id} 

    return stock, options 

 

def index_value(mid): 

    return weights.dot(mid) / 1000 

 

def index_future_theo(product, x): 

    T = calculate_current_time_to_date(instruments[product].expiry) 

    theo = x * np.exp(r * T) 

    return theo 

 

def retreat(delta): 

    return delta / 500 # Make a little less aggressive for more products 

 

def calculate_index_delta(total): 

    index_delta = 0 

 

    for item in index_futures: 

        index_delta += total[item] 

 

    index_delta += total['OB5X_ETF'] * 0.25 

 

    for item in index_options: 

        index_delta += total[item] * calculate_option_delta( 

            expiry_date = instruments[item].expiry, 

            strike = instruments[item].strike, 

            option_kind = instruments[item].option_kind, 

            stock_value = x, 

            interest_rate = r, 

            volatility = 1.50 

        ) 

 

    return index_delta 

 

def calculate_equity_delta(total): 

    futures_delta = 0 

 

    for future in equity_futures: 

        futures_delta += total[future] 

 

    return futures_delta 

 
 
 

while True: 

 

    print('-'*40) 

    credit = 0.20 

 

    midpoints = [] 

    for stock in stocks: 

        mid = get_midpoint_value(stock) 

        midpoints.append(mid) 

 

    if not None in midpoints: 

        x = index_value(midpoints)  

        etf = 2.50 + 0.25 * x 

    else: 

        if not get_midpoint_value('OB5X_ETF'): 

            time.sleep(1) 

            x = (get_midpoint_value('OB5X_ETF') - 2.50) / 0.25 

        x = (get_midpoint_value('OB5X_ETF') - 2.50) / 0.25 

 

    spreads_dict = {i: 0.5 for i in all_used} 

    for i in all_used: 

        order_book = exchange.get_last_price_book(i) 

        if (order_book and order_book.bids and order_book.asks): 

            best_bid = order_book.bids[0].price 

            best_ask = order_book.asks[0].price 

            spread = best_ask - best_bid 

            spreads_dict[i] = spread 

        else: 

            time.sleep(2) 

            continue 

 

         

 

    optimal_credit = {key: round(((value - 0.1) / 2), 2) for key, value in spreads_dict.items()} 

             

    t1 = dt.datetime.now() 

 

     

    # INDEX FUTURES 

    total = exchange.get_positions() 

 

    index_delta = calculate_index_delta(total) 

 

    if index_delta >= 0: 

        adjustment = min(retreat(index_delta), credit) #Make credit later on 

    elif index_delta < 0: 

        adjustment = max(retreat(index_delta), -credit) 

 

    for item in index_futures: 

        exchange.delete_orders(item) 

        opti_credit = optimal_credit[item] 

        if opti_credit is not None: 

            opt_credit = opti_credit 

        else: 

            opt_credit = credit 

        theo = index_future_theo(item, x) 

        bid_price = round_down_to_tick(theo - opt_credit - adjustment, tick) 

        ask_price = round_up_to_tick(theo + opt_credit - adjustment, tick) 

 

        net = exchange.get_positions()[item] 

        bid_volume = min(volume, (100 - net)) 

        ask_volume = min(volume, (100 + net)) 

 

        if bid_volume > 0: 

            if exchange.insert_order(instrument_id=item, price=bid_price, volume=bid_volume, side='bid', order_type='limit'): 

                print(f'{item} bid placed at {bid_price} with {bid_volume} volume') 

 

        if ask_volume > 0: 

            if exchange.insert_order(instrument_id=item, price=ask_price, volume=ask_volume, side='ask', order_type='limit'): 

                print(f'{item} ask placed at {ask_price} with {ask_volume} volume') 

 

    t2 = dt.datetime.now() 

    print(f'Index futures time: {t2 - t1}') 

 

    time.sleep(0.25) 

 

    # INDEX OPTIONS 

     

 

    t3 = dt.datetime.now() 

 

    total = exchange.get_positions() 

    index_delta = calculate_index_delta(total) 

 

    if index_delta >= 0: 

        adjustment = min(retreat(index_delta), credit) 

    elif index_delta <0: 

        adjustment = max(retreat(index_delta), -credit) 

 

    for item in index_options: 

        exchange.delete_orders(item) 

        opti_credit = optimal_credit[item] 

        if opti_credit is not None: 

            opt_credit = opti_credit  

        else: 

            opt_credit = credit 

        theo = calculate_theoretical_option_value( 

            expiry = instruments[item].expiry, 

            strike = instruments[item].strike, 

            option_kind = instruments[item].option_kind, 

            stock_value = x, # Maybe recalculate? 

            interest_rate = r,  

            volatility = 1.50 

        ) 

 

        if instruments[item].option_kind == OptionKind.PUT: 

            bid_price = round_down_to_tick(theo - opt_credit + adjustment, tick) 

            ask_price = round_up_to_tick(theo + opt_credit + adjustment, tick) 

 

        if instruments[item].option_kind == OptionKind.CALL: 

            bid_price = round_down_to_tick(theo - opt_credit - adjustment, tick) 

            ask_price = round_up_to_tick(theo + opt_credit - adjustment, tick) 

 

        net = exchange.get_positions()[item] 

        bid_volume = min(volume, (100 - net)) 

        ask_volume = min(volume, (100 + net)) 

 

        if bid_volume > 0: 

            if exchange.insert_order(instrument_id=item, price=bid_price, volume=bid_volume, side='bid', order_type='limit'): 

                print(f'{item} bid placed at {bid_price} with {bid_volume} volume') 

 

        if ask_volume > 0: 

            if exchange.insert_order(instrument_id=item, price=ask_price, volume=ask_volume, side='ask', order_type='limit'): 

                print(f'{item} ask placed at {ask_price} with {ask_volume} volume') 

 

        time.sleep(0.15) 

 

    t4 = dt.datetime.now() 

    print(f'Option loop time: {t4 - t3}') 

     

 

    # EQUITY FUTURES 

    total = exchange.get_positions() 

    equity_delta = calculate_equity_delta(total) 

    if equity_delta >= 0: 

        adjustment = min(retreat(equity_delta), credit)  

    elif equity_delta < 0: 

        adjustment = max(retreat(equity_delta), -credit) 

 

     

 

    for item in equity_futures: 

        exchange.delete_orders(item) 

        opti_credit = optimal_credit[item] 

        if opti_credit is not None: 

            opt_credit = opti_credit 

        else: 

            opt_credit = credit 

        maturity = instruments[item].expiry 

        T = calculate_current_time_to_date(maturity) 

        spot = get_midpoint_value('NVDA') 

        theo = spot * np.exp(0.03 * T) 

 

        bid_price = round_down_to_tick(theo - opt_credit - adjustment, tick) 

        ask_price = round_up_to_tick(theo + opt_credit - adjustment, tick) 

 

        net = exchange.get_positions()[item] 

        bid_volume = min(volume, (100 - net)) 

        ask_volume = min(volume, (100 + net)) 

 

        if bid_volume > 0: 

            if exchange.insert_order(instrument_id=item, price=bid_price, volume=bid_volume, side='bid', order_type='limit'): 

                print(f'{item} bid placed at {bid_price} with {bid_volume} volume') 

 

        if ask_volume > 0: 

            if exchange.insert_order(instrument_id=item, price=ask_price, volume=ask_volume, side='ask', order_type='limit'): 

                print(f'{item} ask placed at {ask_price} with {ask_volume} volume') 

        time.sleep(0.15) 

 

    time.sleep(0.25) 

 
 
 
 
 
 

 
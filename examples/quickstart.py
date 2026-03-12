from nubra_python_sdk.marketdata.market_data import MarketData
from nubra_python_sdk.refdata.instruments import InstrumentData
from nubra_python_sdk.start_sdk import InitNubraSdk, NubraEnv
from nubra_python_sdk.trading.trading_data import NubraTrader
from nubra_python_sdk.trading.trading_enum import DeliveryTypeEnum, ExchangeEnum

from nubra_flexi_payload import build_flexi_payload, build_option_strategy, quote_fetcher_factory

nubra = InitNubraSdk(NubraEnv.UAT, env_creds=True)
instruments = InstrumentData(nubra)
md = MarketData(nubra)
trade = NubraTrader(nubra, version="V2")

symbols = build_option_strategy(
    underlying="NIFTY",
    legs=[
        [23500, "PE", "week0", "SELL", 1],
        [23900, "CE", "week0", "SELL", 1],
    ],
)

payload = build_flexi_payload(
    symbols=symbols,
    instruments_df=instruments.get_instruments_dataframe(exchange="NSE"),
    quote_fetcher=quote_fetcher_factory(md),
    basket_name="AutoBuiltFlexiStrategy",
    tag="auto_entry",
    exchange=ExchangeEnum.NSE,
    multiplier=3,
    order_delivery_type=DeliveryTypeEnum.ORDER_DELIVERY_TYPE_CNC,
    limit_buffer_paise=500,
)

print(payload)
#trade.flexi_order(payload)


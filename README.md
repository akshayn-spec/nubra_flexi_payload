# nubra_flexi_payload

Build Nubra flexi basket payloads from grouped option strategy input.

## Install

```bash
pip install nubra-flexi-payload
```

## Public API

- `build_option_strategy(...)`
- `build_flexi_payload(...)`
- `quote_fetcher_factory(md_instance)`

## Usage

```python
from nubra_python_sdk.marketdata.market_data import MarketData
from nubra_python_sdk.refdata.instruments import InstrumentData
from nubra_python_sdk.start_sdk import InitNubraSdk, NubraEnv
from nubra_python_sdk.trading.trading_data import NubraTrader
from nubra_python_sdk.trading.trading_enum import DeliveryTypeEnum, ExchangeEnum

from nubra_flexi_payload import build_option_strategy, build_flexi_payload, quote_fetcher_factory

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

trade.flexi_order(payload)
```

## Leg Input

Each leg can be passed as either:

- `[strike, option_type, expiry_type, side, lots]`
- `{"strike": 302.5, "option_type": "PE", "expiry_type": "week1", "side": "BUY", "lots": 1}`

Supported `expiry_type` values:

- `week0`: current or nearest live expiry
- `week1`: next expiry after `week0`
- `week2`: next expiry after `week1`
- `week3`: next expiry after `week2`
- `month`: current month's monthly expiry

If a requested weekly expiry is not available for that underlying, the module falls back to the current month's monthly expiry.

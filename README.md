# nubra_flexi_payload

`nubra_flexi_payload` is a small builder for dynamic Nubra flexi basket payloads.

The goal is to let a user define multi-leg option strategies in a simple format, resolve the correct instruments from the instrument master, calculate quantities from lot sizes, and generate a ready-to-send `trade.flexi_order(...)` payload without doing the repetitive symbol, expiry, quantity, and pricing calculations manually.

It is designed for flexible strategy construction across different underlyings and exchanges, while keeping Nubra SDK initialization outside the package. The package also builds an aggressive basket limit price so the flexi basket behaves like a marketable order and gets placed seamlessly.

## Install

```bash
pip install nubra-flexi-payload
```

## Public API

- `build_option_strategy(...)`
- `build_flexi_payload(...)`
- `quote_fetcher_factory(md_instance)`

## What It Handles

- Build grouped strategy input from a single underlying and multiple option legs
- Resolve correct option instruments from a preloaded instrument master
- Support relative expiry inputs like `week0`, `week1`, `week2`, `week3`, and `month`
- Calculate per-leg quantity from instrument lot size and requested lots
- Build the final `trade.flexi_order(...)` payload
- Set an aggressive basket limit price so the flexi order gets placed without extra strategy-premium calculations from the user

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

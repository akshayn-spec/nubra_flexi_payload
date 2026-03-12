# nubra_flexi_payload

Build Nubra flexi basket payloads from grouped option strategy input.

## Install

```bash
pip install nubra_flexi_payload
```

## Public API

- `build_option_strategy(...)`
- `build_flexi_payload(...)`
- `quote_fetcher_factory(md_instance)`

## Usage

```python
from nubra_flexi_payload import build_option_strategy, build_flexi_payload, quote_fetcher_factory


symbols = build_option_strategy(
    underlying="ITC",
    legs=[
        [302.5, "PE", "week1", "BUY", 1],
        [315, "CE", "week1", "BUY", 1],
    ],
)

payload = build_flexi_payload(
    symbols=symbols,
    instruments_df=instruments_df,
    quote_fetcher=quote_fetcher_factory(md),
    basket_name="AutoBuiltFlexiStrategy",
    tag="auto_entry",
    exchange="NSE",
    multiplier=3,
    order_delivery_type="ORDER_DELIVERY_TYPE_CNC",
    limit_buffer_paise=500,
)

trade.flexi_order(payload)
```

## Leg Input

Each leg can be passed as either:

- `[strike, option_type, expiry_type, side, lots]`
- `{"strike": 302.5, "option_type": "PE", "expiry_type": "week1", "side": "BUY", "lots": 1}`

Supported `expiry_type` values:

- `week0`
- `week1`
- `week2`
- `week3`
- `month`

from datetime import date
from typing import Callable, Dict, List, Sequence, Union

import pandas as pd

EXPIRY_INDEX_MAP = {"week0": 0, "week1": 1, "week2": 2, "week3": 3}
REQUIRED_INSTRUMENT_COLUMNS = {"exchange", "asset", "derivative_type", "expiry", "strike_price", "asset_type", "lot_size", "ref_id"}
BUY_SIDE = "ORDER_SIDE_BUY"
SELL_SIDE = "ORDER_SIDE_SELL"


def _enum_value(value):
    return getattr(value, "value", value)


def quote_fetcher_factory(md_instance):
    def quote_fetcher(ref_id, order_side):
        quote = md_instance.quote(ref_id=ref_id, levels=1)
        ob = quote.orderBook

        if order_side == BUY_SIDE and getattr(ob, "ask", None):
            return float(ob.ask[0].price)
        if order_side == SELL_SIDE and getattr(ob, "bid", None):
            return float(ob.bid[0].price)

        ltp = getattr(ob, "last_traded_price", None)
        if ltp is None:
            ltp = getattr(ob, "ltp", None)
        if ltp is None:
            raise ValueError(f"LTP not available for ref_id: {ref_id}")

        return float(ltp)

    return quote_fetcher


def _normalize_leg(underlying: str, leg: Union[Dict, Sequence]) -> Dict[str, Union[str, float, int]]:
    if isinstance(leg, dict):
        strike = leg["strike"]
        option_type = leg["option_type"]
        expiry_type = leg["expiry_type"]
        side = leg["side"]
        lots = leg.get("lots", 1)
    else:
        if len(leg) != 5:
            raise ValueError("Each leg sequence must be [strike, option_type, expiry_type, side, lots]")
        strike, option_type, expiry_type, side, lots = leg

    option_type = str(option_type).upper().strip()
    expiry_type = str(expiry_type).lower().strip()
    side = str(side).upper().strip()
    lots = int(lots)

    if option_type not in ("CE", "PE"):
        raise ValueError("option_type must be CE or PE")
    if side not in ("BUY", "SELL"):
        raise ValueError("side must be BUY or SELL")
    if expiry_type not in (*EXPIRY_INDEX_MAP.keys(), "month"):
        raise ValueError("expiry_type must be one of: week0, week1, week2, week3, month")
    if lots <= 0:
        raise ValueError("lots must be greater than 0")

    return {
        "underlying": underlying,
        "strike": float(strike),
        "option_type": option_type,
        "expiry_type": expiry_type,
        "side": side,
        "lots": lots,
    }


def build_option_strategy(*, underlying: str, legs: List[Union[Dict, Sequence]]) -> Dict[str, List[Dict[str, Union[str, float, int]]]]:
    underlying = underlying.upper().strip()
    if not underlying:
        raise ValueError("underlying is required")
    if not legs:
        raise ValueError("legs must contain at least one leg")

    return {
        "underlying": underlying,
        "legs": [_normalize_leg(underlying, leg) for leg in legs],
    }


def _validate_instruments_df(instruments_df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(instruments_df, pd.DataFrame):
        raise TypeError("instruments_df must be a pandas DataFrame")
    missing = REQUIRED_INSTRUMENT_COLUMNS.difference(instruments_df.columns)
    if missing:
        raise ValueError(f"instruments_df missing required columns: {sorted(missing)}")
    return instruments_df


def _get_option_universe(instruments_df: pd.DataFrame, underlying: str, exchange: str) -> pd.DataFrame:
    df = _validate_instruments_df(instruments_df)
    option_df = df[
        (df["exchange"] == exchange)
        & (df["asset"] == underlying)
        & (df["derivative_type"] == "OPT")
    ].copy()

    if option_df.empty:
        raise ValueError(f"No option instruments found for underlying: {underlying}")

    option_df["expiry"] = pd.to_numeric(option_df["expiry"], errors="coerce").astype("Int64")
    option_df["strike_price"] = pd.to_numeric(option_df["strike_price"], errors="coerce")
    option_df = option_df.dropna(subset=["expiry", "strike_price"])

    if option_df.empty:
        raise ValueError(f"Option universe is empty after parsing for underlying: {underlying}")

    return option_df


def _resolve_expiry(instruments_df: pd.DataFrame, underlying: str, expiry_type: str, exchange: str) -> int:
    option_df = _get_option_universe(instruments_df, underlying, exchange)
    today_value = int(date.today().strftime("%Y%m%d"))
    expiries = sorted(expiry for expiry in option_df["expiry"].astype(int).unique().tolist() if expiry >= today_value)

    if not expiries:
        raise ValueError(f"No live expiries found for underlying: {underlying}")

    current_year_month = int(date.today().strftime("%Y%m"))
    monthly_expiries = [expiry for expiry in expiries if expiry // 100 == current_year_month]
    if not monthly_expiries:
        raise ValueError(f"No current-month expiry found for {underlying} in {current_year_month}")

    monthly_fallback = monthly_expiries[-1]
    if expiry_type in EXPIRY_INDEX_MAP:
        expiry_index = EXPIRY_INDEX_MAP[expiry_type]
        return expiries[expiry_index] if expiry_index < len(expiries) else monthly_fallback
    return monthly_fallback


def _resolve_option_instrument(instruments_df: pd.DataFrame, leg: Dict[str, Union[str, float, int]], exchange: str) -> Dict[str, Union[str, float, int]]:
    underlying = str(leg["underlying"])
    option_df = _get_option_universe(instruments_df, underlying, exchange)
    expiry = _resolve_expiry(instruments_df, underlying, str(leg["expiry_type"]), exchange)
    strike_price = int(round(float(leg["strike"]) * 100))
    option_type = str(leg["option_type"])
    asset_type = option_df["asset_type"].dropna().iloc[0]

    matches = option_df[
        (option_df["expiry"].astype(int) == expiry)
        & (option_df["strike_price"].astype(int) == strike_price)
        & (option_df["option_type"] == option_type)
        & (option_df["asset_type"] == asset_type)
    ]

    if matches.empty:
        raise ValueError(f"Instrument not found for {underlying} {option_type} {leg['strike']} {leg['expiry_type']}")

    row = matches.iloc[0]
    return {
        "ref_id": int(row["ref_id"]),
        "lot_size": int(row["lot_size"]),
    }


def _build_orders(symbols: Dict[str, List[Dict[str, Union[str, float, int]]]], instruments_df: pd.DataFrame, exchange: str, order_qty: int = None) -> List[Dict[str, Union[str, int]]]:
    side_map = {"BUY": BUY_SIDE, "SELL": SELL_SIDE}
    orders = []

    for leg in symbols["legs"]:
        instrument = _resolve_option_instrument(instruments_df, leg, exchange)
        qty = int(order_qty) if order_qty is not None else instrument["lot_size"] * int(leg["lots"])
        orders.append({
            "ref_id": instrument["ref_id"],
            "order_qty": qty,
            "order_side": side_map[str(leg["side"])],
        })

    return orders


def _get_signed_strategy_price(orders: List[Dict[str, Union[str, int]]], quote_fetcher: Callable[[int, str], float]) -> float:
    total = 0.0
    for order in orders:
        ref_id = int(order["ref_id"])
        order_side = str(order["order_side"])
        leg_price = float(quote_fetcher(ref_id, order_side))
        total += leg_price if order_side == BUY_SIDE else -leg_price
    return total


def _get_aggressive_entry_price(orders: List[Dict[str, Union[str, int]]], quote_fetcher: Callable[[int, str], float], limit_buffer_paise: int) -> int:
    if limit_buffer_paise < 0:
        raise ValueError("limit_buffer_paise must be >= 0")
    strategy_price = abs(_get_signed_strategy_price(orders, quote_fetcher))
    return int(round(strategy_price + limit_buffer_paise))


def build_flexi_payload(
    *,
    symbols: Dict[str, List[Dict[str, Union[str, float, int]]]],
    instruments_df: pd.DataFrame,
    quote_fetcher: Callable[[int, str], float],
    basket_name: str,
    tag: str,
    exchange: Union[str, object],
    multiplier: int,
    order_delivery_type: Union[str, object] = "ORDER_DELIVERY_TYPE_CNC",
    limit_buffer_paise: int = 500,
    order_qty: int = None,
    price_type: Union[str, object] = "LIMIT",
) -> Dict:
    if "legs" not in symbols:
        raise ValueError("symbols must be created by build_option_strategy(...)")
    if not callable(quote_fetcher):
        raise TypeError("quote_fetcher must be callable")

    exchange_value = _enum_value(exchange)
    order_delivery_type_value = _enum_value(order_delivery_type)
    price_type_value = _enum_value(price_type)

    orders = _build_orders(symbols, instruments_df, str(exchange_value), order_qty=order_qty)
    entry_price = _get_aggressive_entry_price(orders, quote_fetcher, limit_buffer_paise)

    return {
        "exchange": exchange,
        "basket_name": basket_name,
        "tag": tag,
        "orders": orders,
        "basket_params": {
            "order_side": BUY_SIDE,
            "order_delivery_type": order_delivery_type_value,
            "price_type": price_type_value,
            "entry_price": entry_price,
            "multiplier": multiplier,
        },
    }

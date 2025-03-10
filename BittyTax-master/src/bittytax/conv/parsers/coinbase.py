# -*- coding: utf-8 -*-
# (c) Nano Nano Ltd 2019

import re
import sys
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional, Tuple

from colorama import Fore
from typing_extensions import Unpack

from ...bt_types import TrType, UnmappedType
from ...config import config
from ...constants import WARNING
from ..dataparser import DataParser, ParserArgs, ParserType
from ..datarow import TxRawPos
from ..exceptions import UnexpectedContentError, UnexpectedTypeError
from ..out_record import TransactionOutRecord

if TYPE_CHECKING:
    from ..datarow import DataRow

WALLET = "Coinbase"
DUPLICATE = UnmappedType("Duplicate")


def parse_coinbase_v4(
    data_row: "DataRow", parser: DataParser, **_kwargs: Unpack[ParserArgs]
) -> None:
    row_dict = data_row.row_dict
    data_row.timestamp = DataParser.parse_timestamp(row_dict["Timestamp"])

    currency = row_dict["Price Currency"]
    spot_price_ccy = DataParser.convert_currency(
        row_dict["Price at Transaction"].strip("£€$").replace(",", ""),
        currency,
        data_row.timestamp,
    )
    subtotal_ccy = DataParser.convert_currency(
        row_dict["Subtotal"].strip("£€$").replace(",", ""),
        currency,
        data_row.timestamp,
    )
    total_ccy = DataParser.convert_currency(
        row_dict["Total (inclusive of fees and/or spread)"].strip("£€$").replace(",", ""),
        currency,
        data_row.timestamp,
    )
    fees_ccy = DataParser.convert_currency(
        re.sub(r"[^-\d.]+", "", row_dict["Fees and/or Spread"]),
        currency,
        data_row.timestamp,
    )

    _do_parse_coinbase(
        data_row, parser, (spot_price_ccy, subtotal_ccy, total_ccy, fees_ccy, currency)
    )


def parse_coinbase_v3(
    data_row: "DataRow", parser: DataParser, **_kwargs: Unpack[ParserArgs]
) -> None:
    row_dict = data_row.row_dict
    data_row.timestamp = DataParser.parse_timestamp(row_dict["Timestamp"])

    currency = row_dict["Spot Price Currency"]
    spot_price_ccy = DataParser.convert_currency(
        row_dict["Spot Price at Transaction"],
        currency,
        data_row.timestamp,
    )
    subtotal_ccy = DataParser.convert_currency(
        row_dict["Subtotal"],
        currency,
        data_row.timestamp,
    )
    total_ccy = DataParser.convert_currency(
        row_dict["Total (inclusive of fees and/or spread)"],
        currency,
        data_row.timestamp,
    )
    fees_ccy = DataParser.convert_currency(
        row_dict["Fees and/or Spread"],
        currency,
        data_row.timestamp,
    )

    _do_parse_coinbase(
        data_row, parser, (spot_price_ccy, subtotal_ccy, total_ccy, fees_ccy, currency)
    )


def parse_coinbase_v2(
    data_row: "DataRow", parser: DataParser, **_kwargs: Unpack[ParserArgs]
) -> None:
    row_dict = data_row.row_dict
    data_row.timestamp = DataParser.parse_timestamp(row_dict["Timestamp"])

    currency = row_dict["Spot Price Currency"]
    spot_price_ccy = DataParser.convert_currency(
        row_dict["Spot Price at Transaction"],
        currency,
        data_row.timestamp,
    )
    subtotal_ccy = DataParser.convert_currency(
        row_dict["Subtotal"],
        currency,
        data_row.timestamp,
    )
    total_ccy = DataParser.convert_currency(
        row_dict["Total (inclusive of fees)"],
        currency,
        data_row.timestamp,
    )
    fees_ccy = DataParser.convert_currency(
        row_dict["Fees"],
        currency,
        data_row.timestamp,
    )

    _do_parse_coinbase(
        data_row, parser, (spot_price_ccy, subtotal_ccy, total_ccy, fees_ccy, currency)
    )


def parse_coinbase_v1(
    data_row: "DataRow", parser: DataParser, **_kwargs: Unpack[ParserArgs]
) -> None:
    row_dict = data_row.row_dict
    data_row.timestamp = DataParser.parse_timestamp(row_dict["Timestamp"])

    currency = parser.args[0].group(1)
    spot_price_ccy = DataParser.convert_currency(
        row_dict[f"{currency} Spot Price at Transaction"], currency, data_row.timestamp
    )
    subtotal_ccy = DataParser.convert_currency(
        row_dict[f"{currency} Subtotal"], currency, data_row.timestamp
    )
    total_ccy = DataParser.convert_currency(
        row_dict[f"{currency} Total (inclusive of fees)"], currency, data_row.timestamp
    )
    fees_ccy = DataParser.convert_currency(
        row_dict[f"{currency} Fees"], currency, data_row.timestamp
    )

    _do_parse_coinbase(
        data_row, parser, (spot_price_ccy, subtotal_ccy, total_ccy, fees_ccy, currency)
    )


def _do_parse_coinbase(
    data_row: "DataRow",
    parser: DataParser,
    fiat_values: Tuple[
        Optional[Decimal], Optional[Decimal], Optional[Decimal], Optional[Decimal], str
    ],
) -> None:
    (spot_price_ccy, subtotal_ccy, total_ccy, fees_ccy, currency) = fiat_values
    row_dict = data_row.row_dict

    if row_dict["Transaction Type"] == "Deposit":
        # Fiat deposit
        data_row.t_record = TransactionOutRecord(
            TrType.DEPOSIT,
            data_row.timestamp,
            buy_quantity=(
                Decimal(row_dict["Quantity Transacted"]) + abs(fees_ccy)
                if fees_ccy
                else Decimal(row_dict["Quantity Transacted"])
            ),
            buy_asset=row_dict["Asset"],
            fee_quantity=fees_ccy,
            fee_asset=row_dict["Asset"],
            wallet=WALLET,
        )
    elif row_dict["Transaction Type"] == "Withdrawal":
        # Fiat withdrawal
        data_row.t_record = TransactionOutRecord(
            TrType.WITHDRAWAL,
            data_row.timestamp,
            sell_quantity=(
                Decimal(row_dict["Quantity Transacted"]) - abs(fees_ccy)
                if fees_ccy
                else Decimal(row_dict["Quantity Transacted"])
            ),
            sell_asset=row_dict["Asset"],
            fee_quantity=abs(fees_ccy) if fees_ccy is not None else None,
            fee_asset=row_dict["Asset"],
            wallet=WALLET,
        )
    elif row_dict["Transaction Type"] in ("Exchange Deposit", "Pro Deposit"):
        # Withdrawal to Coinbase Pro
        data_row.t_record = TransactionOutRecord(
            TrType.WITHDRAWAL,
            data_row.timestamp,
            sell_quantity=Decimal(row_dict["Quantity Transacted"]),
            sell_asset=row_dict["Asset"],
            wallet=WALLET,
        )
    elif row_dict["Transaction Type"] in ("Exchange Withdrawal", "Pro Withdrawal"):
        # Deposit from Coinbase Pro
        data_row.t_record = TransactionOutRecord(
            TrType.DEPOSIT,
            data_row.timestamp,
            buy_quantity=Decimal(row_dict["Quantity Transacted"]),
            buy_asset=row_dict["Asset"],
            wallet=WALLET,
        )
    elif row_dict["Transaction Type"] == "Receive":
        # Calculate the buy_value from the spot price if available
        if spot_price_ccy:
            buy_value = spot_price_ccy * Decimal(row_dict["Quantity Transacted"])
        else:
            buy_value = None

        if "Coinbase Referral" in row_dict["Notes"]:
            data_row.t_record = TransactionOutRecord(
                TrType.REFERRAL,
                data_row.timestamp,
                buy_quantity=Decimal(row_dict["Quantity Transacted"]),
                buy_asset=row_dict["Asset"],
                buy_value=buy_value,
                wallet=WALLET,
            )
        elif "Coinbase Earn" in row_dict["Notes"] or "Coinbase Rewards" in row_dict["Notes"]:
            data_row.t_record = TransactionOutRecord(
                TrType.INCOME,
                data_row.timestamp,
                buy_quantity=Decimal(row_dict["Quantity Transacted"]),
                buy_asset=row_dict["Asset"],
                buy_value=buy_value,
                wallet=WALLET,
            )
        else:
            # Crypto deposit
            data_row.t_record = TransactionOutRecord(
                TrType.DEPOSIT,
                data_row.timestamp,
                buy_quantity=Decimal(row_dict["Quantity Transacted"]),
                buy_asset=row_dict["Asset"],
                wallet=WALLET,
            )
    elif row_dict["Transaction Type"] in (
        "Coinbase Earn",
        "Learning Reward",
    ):
        data_row.t_record = TransactionOutRecord(
            TrType.INCOME,
            data_row.timestamp,
            buy_quantity=Decimal(row_dict["Quantity Transacted"]),
            buy_asset=row_dict["Asset"],
            buy_value=total_ccy,
            wallet=WALLET,
        )
    elif row_dict["Transaction Type"] in (
        "Rewards Income",
        "Reward Income",
        "Inflation Reward",
        "Staking Income",
    ):
        data_row.t_record = TransactionOutRecord(
            TrType.STAKING,
            data_row.timestamp,
            buy_quantity=Decimal(row_dict["Quantity Transacted"]),
            buy_asset=row_dict["Asset"],
            buy_value=total_ccy,
            wallet=WALLET,
        )
    elif row_dict["Transaction Type"] == "Subscription Rebates (24 Hours)":
        data_row.t_record = TransactionOutRecord(
            TrType.FEE_REBATE,
            data_row.timestamp,
            buy_quantity=Decimal(row_dict["Quantity Transacted"]),
            buy_asset=row_dict["Asset"],
            buy_value=total_ccy,
            wallet=WALLET,
        )
    elif row_dict["Transaction Type"] == "Send":
        # Crypto withdrawal
        data_row.tx_raw = TxRawPos(tx_dest_pos=parser.in_header.index("Notes"))
        data_row.t_record = TransactionOutRecord(
            TrType.WITHDRAWAL,
            data_row.timestamp,
            sell_quantity=Decimal(row_dict["Quantity Transacted"]),
            sell_asset=row_dict["Asset"],
            wallet=WALLET,
        )
    elif row_dict["Transaction Type"] in ("Buy", "Advanced Trade Buy", "Advance Trade Buy"):
        note_currency, quote = _get_note_currency(row_dict["Notes"])
        if note_currency is None:
            raise UnexpectedContentError(
                parser.in_header.index("Notes"), "Notes", row_dict["Notes"]
            )

        if quote != currency:
            if parser.in_header_row_num is None:
                raise RuntimeError("Missing in_header_row_num")

            sys.stderr.write(
                f"{Fore.YELLOW}row[{parser.in_header_row_num + data_row.line_num}] {data_row}\n"
                f"{WARNING} {quote} amount/fee is not availabe so will not balance, "
                f"using {currency} instead\n"
            )

        if (
            config.coinbase_zero_fees_are_gifts
            and row_dict["Transaction Type"] == "Buy"
            and fees_ccy == 0
        ):
            # Zero fees "may" indicate an early referral reward, or airdrop
            data_row.t_record = TransactionOutRecord(
                TrType.REFERRAL,
                data_row.timestamp,
                buy_quantity=Decimal(row_dict["Quantity Transacted"]),
                buy_asset=row_dict["Asset"],
                buy_value=total_ccy if total_ccy and total_ccy > 0 else None,
                wallet=WALLET,
            )
        else:
            data_row.t_record = TransactionOutRecord(
                TrType.TRADE,
                data_row.timestamp,
                buy_quantity=Decimal(row_dict["Quantity Transacted"]),
                buy_asset=row_dict["Asset"],
                sell_quantity=subtotal_ccy,
                sell_asset=config.ccy,
                fee_quantity=abs(fees_ccy) if fees_ccy is not None else None,
                fee_asset=config.ccy,
                wallet=WALLET,
            )
    elif row_dict["Transaction Type"] in ("Sell", "Advanced Trade Sell", "Advance Trade Sell"):
        note_currency, quote = _get_note_currency(row_dict["Notes"])
        if note_currency is None:
            raise UnexpectedContentError(
                parser.in_header.index("Notes"), "Notes", row_dict["Notes"]
            )

        if quote != currency:
            if parser.in_header_row_num is None:
                raise RuntimeError("Missing in_header_row_num")

            sys.stderr.write(
                f"{Fore.YELLOW}row[{parser.in_header_row_num + data_row.line_num}] {data_row}\n"
                f"{WARNING} {quote} amount/fee is not available so will not balance, "
                f"using {currency} instead\n"
            )

        data_row.t_record = TransactionOutRecord(
            TrType.TRADE,
            data_row.timestamp,
            buy_quantity=subtotal_ccy,
            buy_asset=config.ccy,
            sell_quantity=Decimal(row_dict["Quantity Transacted"]),
            sell_asset=row_dict["Asset"],
            fee_quantity=abs(fees_ccy) if fees_ccy is not None else None,
            fee_asset=config.ccy,
            wallet=WALLET,
        )
    elif row_dict["Transaction Type"] == "Convert":
        convert_info = _get_convert_info(row_dict["Notes"])
        if convert_info is None:
            raise UnexpectedContentError(
                parser.in_header.index("Notes"), "Notes", row_dict["Notes"]
            )

        buy_quantity = Decimal(convert_info[2].replace(",", ""))
        buy_asset = convert_info[3]
        data_row.t_record = TransactionOutRecord(
            TrType.TRADE,
            data_row.timestamp,
            buy_quantity=buy_quantity,
            buy_asset=buy_asset,
            buy_value=total_ccy,
            sell_quantity=Decimal(row_dict["Quantity Transacted"]),
            sell_asset=row_dict["Asset"],
            sell_value=total_ccy,
            wallet=WALLET,
        )
    else:
        raise UnexpectedTypeError(
            parser.in_header.index("Transaction Type"),
            "Transaction Type",
            row_dict["Transaction Type"],
        )


def _get_convert_info(notes: str) -> Optional[Tuple[Any, ...]]:
    match = re.match(
        r"^Converted ([\d|,]*\.\d+|[\d|,]+) (\w+) to ([\d|,]*\.\d+|[\d|,]+) (\w+) *$", notes
    )

    if match:
        return match.groups()
    return None


def _get_note_currency(notes: str) -> Tuple[Optional[str], str]:
    match = re.match(r".+for [£€$]?(?:[\d|,]+\.\d+|[\d|,]+) (\w+)(?: on )?(\w+-\w+)?.*$", notes)

    if match:
        currency = quote = match.group(1)
        if match.group(2):
            quote = match.group(2).split("-")[1]
        return currency, quote
    return None, ""


def parse_coinbase_transfers(
    data_row: "DataRow", parser: DataParser, **_kwargs: Unpack[ParserArgs]
) -> None:
    row_dict = data_row.row_dict
    data_row.timestamp = DataParser.parse_timestamp(row_dict["Timestamp"])

    if row_dict["Type"] == "Deposit":
        data_row.t_record = TransactionOutRecord(
            TrType.DEPOSIT,
            data_row.timestamp,
            buy_quantity=Decimal(row_dict["Total"]),
            buy_asset=row_dict["Currency"],
            fee_quantity=Decimal(row_dict["Fees"]),
            fee_asset=row_dict["Currency"],
            wallet=WALLET,
        )
    elif row_dict["Type"] == "Withdrawal":
        data_row.t_record = TransactionOutRecord(
            TrType.WITHDRAWAL,
            data_row.timestamp,
            sell_quantity=Decimal(row_dict["Total"]),
            sell_asset=row_dict["Currency"],
            fee_quantity=Decimal(row_dict["Fees"]),
            fee_asset=row_dict["Currency"],
            wallet=WALLET,
        )
    elif row_dict["Type"] == "Buy":
        data_row.t_record = TransactionOutRecord(
            TrType.TRADE,
            data_row.timestamp,
            buy_quantity=Decimal(row_dict[parser.in_header[2]]),
            buy_asset=parser.in_header[2],
            sell_quantity=Decimal(row_dict["Subtotal"]),
            sell_asset=row_dict["Currency"],
            fee_quantity=Decimal(row_dict["Fees"]),
            fee_asset=row_dict["Currency"],
            wallet=WALLET,
        )
    elif row_dict["Type"] == "Sell":
        data_row.t_record = TransactionOutRecord(
            TrType.TRADE,
            data_row.timestamp,
            buy_quantity=Decimal(row_dict["Subtotal"]),
            buy_asset=row_dict["Currency"],
            sell_quantity=Decimal(row_dict[parser.in_header[2]]),
            sell_asset=parser.in_header[2],
            fee_quantity=Decimal(row_dict["Fees"]),
            fee_asset=row_dict["Currency"],
            wallet=WALLET,
        )
    else:
        raise UnexpectedTypeError(parser.in_header.index("Type"), "Type", row_dict["Type"])


def parse_coinbase_transactions(
    data_row: "DataRow", _parser: DataParser, **_kwargs: Unpack[ParserArgs]
) -> None:
    row_dict = data_row.row_dict
    data_row.timestamp = DataParser.parse_timestamp(row_dict["Timestamp"])

    if data_row.row[21] != "":
        # Hash so must be external crypto deposit or withdrawal
        if Decimal(row_dict["Amount"]) < 0:
            data_row.t_record = TransactionOutRecord(
                TrType.WITHDRAWAL,
                data_row.timestamp,
                sell_quantity=abs(Decimal(row_dict["Amount"])),
                sell_asset=row_dict["Currency"],
                wallet=WALLET,
            )
        else:
            data_row.t_record = TransactionOutRecord(
                TrType.DEPOSIT,
                data_row.timestamp,
                buy_quantity=Decimal(row_dict["Amount"]),
                buy_asset=row_dict["Currency"],
                wallet=WALLET,
            )
    elif row_dict["Transfer ID"] != "":
        # Transfer ID so could be a trade or external fiat deposit/withdrawal
        if row_dict["Currency"] != row_dict["Transfer Total Currency"]:
            # Currencies are different so must be a trade
            if Decimal(row_dict["Amount"]) < 0:
                data_row.t_record = TransactionOutRecord(
                    TrType.TRADE,
                    data_row.timestamp,
                    buy_quantity=Decimal(row_dict["Transfer Total"])
                    + Decimal(row_dict["Transfer Fee"]),
                    buy_asset=row_dict["Transfer Total Currency"],
                    sell_quantity=abs(Decimal(row_dict["Amount"])),
                    sell_asset=row_dict["Currency"],
                    fee_quantity=Decimal(row_dict["Transfer Fee"]),
                    fee_asset=row_dict["Transfer Fee Currency"],
                    wallet=WALLET,
                )
            else:
                data_row.t_record = TransactionOutRecord(
                    TrType.TRADE,
                    data_row.timestamp,
                    buy_quantity=Decimal(row_dict["Amount"]),
                    buy_asset=row_dict["Currency"],
                    sell_quantity=Decimal(row_dict["Transfer Total"])
                    - Decimal(row_dict["Transfer Fee"]),
                    sell_asset=row_dict["Transfer Total Currency"],
                    fee_quantity=Decimal(row_dict["Transfer Fee"]),
                    fee_asset=row_dict["Transfer Fee Currency"],
                    wallet=WALLET,
                )
        else:
            if Decimal(row_dict["Amount"]) < 0:
                data_row.t_record = TransactionOutRecord(
                    TrType.WITHDRAWAL,
                    data_row.timestamp,
                    sell_quantity=Decimal(row_dict["Transfer Total"]),
                    sell_asset=row_dict["Currency"],
                    fee_quantity=Decimal(row_dict["Transfer Fee"]),
                    fee_asset=row_dict["Transfer Fee Currency"],
                    wallet=WALLET,
                )
            else:
                data_row.t_record = TransactionOutRecord(
                    TrType.DEPOSIT,
                    data_row.timestamp,
                    buy_quantity=Decimal(row_dict["Transfer Total"]),
                    buy_asset=row_dict["Currency"],
                    fee_quantity=Decimal(row_dict["Transfer Fee"]),
                    fee_asset=row_dict["Transfer Fee Currency"],
                    wallet=WALLET,
                )
    else:
        # Could be a referral bonus or deposit/withdrawal to/from Coinbase Pro
        if row_dict["Notes"] != "" and row_dict["Currency"] == "BTC":
            # Bonus is always in BTC
            data_row.t_record = TransactionOutRecord(
                TrType.REFERRAL,
                data_row.timestamp,
                buy_quantity=Decimal(row_dict["Amount"]),
                buy_asset=row_dict["Currency"],
                wallet=WALLET,
            )
        elif row_dict["Notes"] != "" and row_dict["Currency"] != "BTC":
            # Special case, flag as duplicate entry, trade will be in BTC Wallet Transactions Report
            if Decimal(row_dict["Amount"]) < 0:
                data_row.t_record = TransactionOutRecord(
                    DUPLICATE,
                    data_row.timestamp,
                    sell_quantity=abs(Decimal(row_dict["Amount"])),
                    sell_asset=row_dict["Currency"],
                    wallet=WALLET,
                )
            else:
                data_row.t_record = TransactionOutRecord(
                    DUPLICATE,
                    data_row.timestamp,
                    buy_quantity=Decimal(row_dict["Amount"]),
                    buy_asset=row_dict["Currency"],
                    wallet=WALLET,
                )
        elif Decimal(row_dict["Amount"]) < 0:
            data_row.t_record = TransactionOutRecord(
                TrType.WITHDRAWAL,
                data_row.timestamp,
                sell_quantity=abs(Decimal(row_dict["Amount"])),
                sell_asset=row_dict["Currency"],
                wallet=WALLET,
            )
        else:
            data_row.t_record = TransactionOutRecord(
                TrType.DEPOSIT,
                data_row.timestamp,
                buy_quantity=Decimal(row_dict["Amount"]),
                buy_asset=row_dict["Currency"],
                wallet=WALLET,
            )


DataParser(
    ParserType.EXCHANGE,
    "Coinbase",
    [
        "ID",  # Added
        "Timestamp",
        "Transaction Type",
        "Asset",
        "Quantity Transacted",
        "Price Currency",
        "Price at Transaction",
        "Subtotal",
        "Total (inclusive of fees and/or spread)",
        "Fees and/or Spread",
        "Notes",
    ],
    worksheet_name="Coinbase",
    row_handler=parse_coinbase_v4,
)

DataParser(
    ParserType.EXCHANGE,
    "Coinbase",
    [
        "Timestamp",
        "Transaction Type",
        "Asset",
        "Quantity Transacted",
        "Price Currency",  # Renamed
        "Price at Transaction",  # Renamed
        "Subtotal",
        "Total (inclusive of fees and/or spread)",
        "Fees and/or Spread",
        "Notes",
    ],
    worksheet_name="Coinbase",
    row_handler=parse_coinbase_v4,
)

DataParser(
    ParserType.EXCHANGE,
    "Coinbase",
    [
        "Timestamp",
        "Transaction Type",
        "Asset",
        "Quantity Transacted",
        "Spot Price Currency",
        "Spot Price at Transaction",
        "Subtotal",
        "Total (inclusive of fees and/or spread)",
        "Fees and/or Spread",
        "Notes",
    ],
    worksheet_name="Coinbase",
    row_handler=parse_coinbase_v3,
)

DataParser(
    ParserType.EXCHANGE,
    "Coinbase",
    [
        "Timestamp",
        "Transaction Type",
        "Asset",
        "Quantity Transacted",
        "Spot Price Currency",
        "Spot Price at Transaction",
        "Subtotal",
        "Total (inclusive of fees)",
        "Fees",
        "Notes",
    ],
    worksheet_name="Coinbase",
    row_handler=parse_coinbase_v2,
)

DataParser(
    ParserType.EXCHANGE,
    "Coinbase",
    [
        "Timestamp",
        "Transaction Type",
        "Asset",
        "Quantity Transacted",
        lambda h: re.match(r"^(\w{3}) Spot Price at Transaction", h),
        lambda h: re.match(r"^(\w{3}) Subtotal", h),
        lambda h: re.match(r"^(\w{3}) Total \(inclusive of fees\)", h),
        lambda h: re.match(r"^(\w{3}) Fees", h),
        "Notes",
    ],
    worksheet_name="Coinbase",
    row_handler=parse_coinbase_v1,
)

DataParser(
    ParserType.EXCHANGE,
    "Coinbase Transfers",
    [
        "Timestamp",
        "Type",
        None,
        "Subtotal",
        "Fees",
        "Total",
        "Currency",
        "Price Per Coin",
        "Payment Method",
        "ID",
        "Share",
    ],
    worksheet_name="Coinbase",
    row_handler=parse_coinbase_transfers,
)

DataParser(
    ParserType.EXCHANGE,
    "Coinbase Transactions",
    [
        "Timestamp",
        "Balance",
        "Amount",
        "Currency",
        "To",
        "Notes",
        "Instantly Exchanged",
        "Transfer Total",
        "Transfer Total Currency",
        "Transfer Fee",
        "Transfer Fee Currency",
        "Transfer Payment Method",
        "Transfer ID",
        "Order Price",
        "Order Currency",
        None,
        "Order Tracking Code",
        "Order Custom Parameter",
        "Order Paid Out",
        "Recurring Payment ID",
        None,
        None,
    ],
    worksheet_name="Coinbase",
    row_handler=parse_coinbase_transactions,
)

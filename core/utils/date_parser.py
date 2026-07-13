# utils/date_parser.py

import re
from datetime import datetime

import pandas as pd
from dateutil import parser


class FlexibleDateParser:
    """
    Parses dates from various formats into YYYY-MM-DD
    """

    @staticmethod
    def parse_date(date_value):
        """
        Parse a date from various formats and return YYYY-MM-DD string
        Handles: Excel serial numbers, strings, datetime objects, etc.
        """
        if pd.isna(date_value) or date_value == "":
            return None

        # If it's already a datetime object
        if isinstance(date_value, (datetime, pd.Timestamp)):
            return date_value.strftime("%Y-%m-%d")

        # If it's a number (Excel serial date)
        if isinstance(date_value, (int, float)):
            try:
                # Convert Excel serial date to datetime
                excel_date = pd.Timestamp.fromordinal(int(date_value) - 693594)
                return excel_date.strftime("%Y-%m-%d")
            except:
                pass

        # If it's a string, try multiple formats
        if isinstance(date_value, str):
            date_value = date_value.strip()

            # Try Persian/Jalali dates first if needed (you can add this)
            # persian_date = FlexibleDateParser.parse_persian_date(date_value)
            # if persian_date:
            #     return persian_date

            # Common Persian date patterns (optional)
            # Example: "1402-08-12", "1402/08/12"
            persian_patterns = [
                r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})",  # 1402-08-12 or 1402/08/12
            ]

            for pattern in persian_patterns:
                match = re.match(pattern, date_value)
                if match:
                    year, month, day = map(int, match.groups())
                    if year > 1000:  # Likely Persian year
                        # You would need a Persian calendar converter here
                        # For now, we'll just store as-is and warn
                        # You can use `persian` or `jdatetime` library
                        pass

            # Try python-dateutil parser (handles many formats)
            try:
                parsed_date = parser.parse(date_value, fuzzy=True)
                return parsed_date.strftime("%Y-%m-%d")
            except:
                pass

            # Try common formats manually
            common_formats = [
                "%Y-%m-%d",  # 2024-08-12
                "%d/%m/%Y",  # 12/08/2024
                "%m/%d/%Y",  # 08/12/2024
                "%d-%m-%Y",  # 12-08-2024
                "%m-%d-%Y",  # 08-12-2024
                "%d.%m.%Y",  # 12.08.2024
                "%b %d, %Y",  # Jan 12, 2024
                "%d %b %Y",  # 12 Jan 2024
                "%B %d, %Y",  # January 12, 2024
                "%d %B %Y",  # 12 January 2024
                "%d %b, %Y",  # 12 Jan, 2024
                "%Y%m%d",  # 20240812
                "%d-%b-%Y",  # 12-Jan-2024
            ]

            for fmt in common_formats:
                try:
                    parsed_date = datetime.strptime(date_value, fmt)
                    return parsed_date.strftime("%Y-%m-%d")
                except ValueError:
                    continue

        # If all parsing fails, log and return None or raise exception
        raise ValueError(f"Unable to parse date: {date_value}")

    @staticmethod
    def parse_persian_date(persian_date_str):
        """
        Optional: Convert Persian/Jalali dates to Gregorian
        Requires: pip install jdatetime
        """
        try:
            import jdatetime

            # Parse Persian date
            if "-" in persian_date_str:
                parts = persian_date_str.split("-")
            elif "/" in persian_date_str:
                parts = persian_date_str.split("/")
            else:
                return None

            if len(parts) == 3:
                year, month, day = map(int, parts)
                gregorian_date = jdatetime.date(year, month, day).togregorian()
                return gregorian_date.strftime("%Y-%m-%d")
        except:
            pass
        return None

    @staticmethod
    def parse_series_to_dates(date_series):
        """
        Parse a pandas Series of dates and return a new Series with parsed dates
        """
        return date_series.apply(FlexibleDateParser.parse_date)

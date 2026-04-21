from enum import Enum


class Currency(str, Enum):
    """
    Supported fiat currencies for CSFloat parser.

    Enum is used to guarantee valid currency values across config
    and prevent invalid runtime strings.
    """

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CAD = "CAD"
    AED = "AED"
    AUD = "AUD"
    BRL = "BRL"
    CHF = "CHF"
    CNY = "CNY"
    CZK = "CZK"
    DKK = "DKK"
    GEL = "GEL"
    HKD = "HKD"
    HUF = "HUF"
    IDR = "IDR"
    ILS = "ILS"
    KHR = "KHR"
    KZT = "KZT"
    MYR = "MYR"
    MXN = "MXN"
    NOK = "NOK"
    NZD = "NZD"
    PLN = "PLN"
    RON = "RON"
    RSD = "RSD"
    SAR = "SAR"
    SEK = "SEK"
    SGD = "SGD"
    THB = "THB"
    TRY = "TRY"
    TWD = "TWD"
    UAH = "UAH"

    @classmethod
    def has_value(cls, value: str) -> bool:
        """
        Check if currency is supported.

        Args:
            value: Currency code string

        Returns:
            bool: True if supported
        """
        return value in cls._value2member_map_

    @classmethod
    def from_str(cls, value: str) -> "Currency":
        """
        Safe conversion from string to Currency enum.

        Args:
            value: Currency code

        Returns:
            Currency enum value

        Raises:
            ValueError: if currency is not supported
        """
        value = value.upper()

        if not cls.has_value(value):
            raise ValueError(f"Unsupported currency: {value}")

        return cls(value)

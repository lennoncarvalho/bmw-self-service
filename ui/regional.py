"""Regional display formatting shared by pages (D-44)."""

from PySide6.QtCore import QLocale


def regional_locale() -> QLocale:
    """Use the system region, or Brazilian formatting when none is configured."""
    locale = QLocale.system()
    return QLocale("pt_BR") if locale.language() == QLocale.Language.C else locale

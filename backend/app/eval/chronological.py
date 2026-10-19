"""Kronolojik (sizinti korumali) veri bolme.

Rastgele bolme, gelecekteki bilginin gecmise sizmasina yol acar. Bu yuzden
egitim/dogrulama/test bolmeleri ZAMANA gore yapilir ve bolmeler arasi zaman
sirasi dogrulanir.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, TypeVar

T = TypeVar("T")


@dataclass
class ChronologicalSplit:
    train: list
    validation: list
    test: list


def split_chronological(
    items: Sequence[T], train_frac: float = 0.6, val_frac: float = 0.2
) -> ChronologicalSplit:
    """Ogelarin ZATEN kronolojik sirali oldugu varsayilir."""
    if not 0 < train_frac < 1 or not 0 <= val_frac < 1 or train_frac + val_frac >= 1:
        raise ValueError("Gecersiz bolme oranlari")
    n = len(items)
    if n == 0:
        return ChronologicalSplit([], [], [])
    n_train = int(n * train_frac)
    n_val = int(n * val_frac)
    if n_train == 0 and n > 0:
        n_train = 1
    train = list(items[:n_train])
    val = list(items[n_train : n_train + n_val])
    test = list(items[n_train + n_val :])
    return ChronologicalSplit(train, val, test)


def assert_no_leakage(train_times, val_times, test_times) -> None:
    """Egitim zamanlarinin dogrulama/test zamanlarindan once oldugunu dogrula."""
    if train_times and val_times and max(train_times) > min(val_times):
        raise AssertionError("Zaman sizintisi: egitim setinde dogrulamadan sonra veri var.")
    if val_times and test_times and max(val_times) > min(test_times):
        raise AssertionError("Zaman sizintisi: dogrulama setinde testten sonra veri var.")
    if train_times and test_times and max(train_times) > min(test_times):
        raise AssertionError("Zaman sizintisi: egitim setinde testten sonra veri var.")

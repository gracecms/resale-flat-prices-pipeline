"""Irreversible de-identification of the Resale Identifier (Req: Data Transformation 9).

Uses HMAC-SHA256 keyed with a secret (loaded from the HASH_SECRET_KEY environment variable,
see .env.example) rather than a plain or publicly-salted hash:

- Irreversible: SHA-256 is a one-way function; there is no computationally feasible way to
  recover the identifier from the hash.
- Preserves uniqueness: HMAC-SHA256 is deterministic (same input + key -> same output), and
  at this dataset's scale (hundreds of thousands of rows) the probability of an accidental
  256-bit hash collision between two *different* identifiers is astronomically small - so
  uniqueness of the identifier column carries over to the hashed column.
- Resists dictionary attacks: the Resale Identifier is actually low-entropy and guessable once
  its construction rule is known (it's built from a handful of small, enumerable components -
  month, town initial, a 3-digit block prefix, a 3-digit price-average prefix). A plain hash,
  or even a hash salted with a *public* per-record salt, would let anyone who knows the
  construction rule regenerate the full candidate space and match hashes straight back to
  identifiers. A secret HMAC key closes that gap: without the key, precomputing a dictionary
  of identifier -> hash pairs is infeasible.
"""
from __future__ import annotations

import hashlib
import hmac
import os

import pandas as pd
from dotenv import load_dotenv

load_dotenv()


def _get_secret_key() -> bytes:
    key = os.environ.get("HASH_SECRET_KEY")
    if not key:
        raise RuntimeError(
            "HASH_SECRET_KEY is not set. Copy .env.example to .env and set a secret value."
        )
    return key.encode("utf-8")


def hash_identifier(identifier: str, secret_key: bytes | None = None) -> str:
    key = secret_key if secret_key is not None else _get_secret_key()
    return hmac.new(key, identifier.encode("utf-8"), hashlib.sha256).hexdigest()


def add_hashed_identifier(df: pd.DataFrame, identifier_column: str = "resale_identifier") -> pd.DataFrame:
    df = df.copy()
    secret_key = _get_secret_key()
    df["hashed_identifier"] = df[identifier_column].apply(lambda v: hash_identifier(v, secret_key))
    assert df["hashed_identifier"].is_unique, "Hashed identifier collision detected"
    return df

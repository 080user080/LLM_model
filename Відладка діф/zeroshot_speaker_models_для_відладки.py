# ukrroberta_zeroshot_from_files.py — призначення мовця (Ukr-RoBERTa mean-pooling)
# -*- coding: utf-8 -*-

import os
import re
import json
import argparse
from typing import List, Dict, Tuple, Optional
from collections import defaultdict


def _safe_field(s: str) -> str:
    out = (s or "").replace("\t", " ").replace("\n", " ").replace("\r", " ")
    # не спамимо тут
    dprint("[DEBUG] _legend_plain_to_json: parsed keys=", list(out.keys())[:10])
    dprint("[DEBUG] build_gid_primary_name: keys=", list(out.keys())[:10])
    return out

def _try_json(s: str):
    try:
        obj = json.loads(s)
        dprint("[DEBUG] _try_json: OK, keys=", list(obj.keys())[:5] if isinstance(obj, dict) else type(obj))
        return obj
    except Exception:
        dprint("[DEBUG] _try_json: not a JSON")
        return None



if __name__ == "__main__":
    main()

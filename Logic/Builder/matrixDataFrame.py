from typing import Tuple, Any, Dict, List
import pandas as pd
from ..converter import coerce_bias_list


def build_matrix_dataframe(matrix: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
    rows: List[Dict[str, str]] = []
    levels: List[str] = []

    for lens_name, result in matrix.items():
        result_dict = result if isinstance(result, dict) else {}
        if result_dict.get("error"):
            rows.append(
                {
                    "Lens": lens_name.capitalize(),
                    "Support": "Error",
                    "Risks": str(result_dict["error"]),
                }
            )
            levels.append("error")
        else:
            biases = coerce_bias_list(result_dict.get("detected_biases"))
            risk_str = (
                ", ".join(
                    b.get("bias", "") if isinstance(b, dict) else str(b)
                    for b in biases
                )
                if biases
                else "None"
            )
            rows.append(
                {
                    "Lens": lens_name.capitalize(),
                    "Support": str(result_dict.get("support_level", "none")).capitalize(),
                    "Risks": risk_str,
                }
            )
            levels.append(str(result_dict.get("support_level", "none")).lower())

    return pd.DataFrame(rows), levels

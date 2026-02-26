import pandas as pd
import json
import os
from typing import Dict, Any

class StrategyLogger:
    """
    Centralized logging module for quantitative trading strategies.
    Standardizes the generation of text reports to ensure consistency across models.
    """
    
    @staticmethod
    def generate_report(
        strategy_name: str,
        asset_info: str,
        parameters: Dict[str, Any],
        performance: Dict[str, Any],
        trade_log: pd.DataFrame
    ) -> str:
        """
        Builds a structured and consistent text report for any strategy.
        """
        report_lines = []
        report_lines.append("="*60)
        report_lines.append(f" DEEP STRATEGY REPORT: {strategy_name.upper()} ({asset_info})")
        report_lines.append("="*60)
        
        report_lines.append("\n[1] STRATEGY PARAMETERS")
        for k, v in parameters.items():
            report_lines.append(f" - {k:<25} {v}")
            
        report_lines.append("\n[2] PERFORMANCE & EXPOSURE SUMMARY")
        for k, v in performance.items():
            report_lines.append(f" - {k:<25} {v}")
            
        report_lines.append("\n[3] DETAILED TRADE LOG & INDICATOR SNAPSHOTS")
        report_lines.append("-" * 60)
        
        if not trade_log.empty:
            df_str = trade_log.to_string(index=False)
            report_lines.append(df_str)
        else:
            report_lines.append("No trades were executed during this period.")
            
        report_lines.append("\n" + "="*60 + "\n")
        return "\n".join(report_lines)

    @staticmethod
    def save_debug_artifacts(
        base_filepath: str,
        asset_info: str,
        parameters: Dict[str, Any],
        performance: Dict[str, Any],
        trade_log: pd.DataFrame,
        results_df: pd.DataFrame = None
    ) -> Dict[str, str]:
        """
        Saves structured logs (JSON and Parquet) specifically designed for LLMs and programmatic ingestion.
        """
        saved_files = {}
        
        # 1. JSON (Discrete Summary & Trade Log)
        json_filepath = base_filepath.replace(".txt", ".json")
        debug_payload = {
            "metadata": {"asset_info": asset_info},
            "parameters": parameters,
            "performance": performance,
            "trades": trade_log.to_dict(orient="records") if not trade_log.empty else []
        }
        
        try:
            with open(json_filepath, "w") as f:
                json.dump(debug_payload, f, indent=4, default=str)
            saved_files['json'] = json_filepath
        except Exception as e:
            print(f"Failed to save JSON artifact: {e}")

        # 2. Parquet (Continuous Math State for Time-Travel Debugging)
        if results_df is not None and not results_df.empty:
            parquet_filepath = base_filepath.replace(".txt", ".parquet")
            try:
                # We need to make sure index is converted for Parquet to work easily
                df_to_save = results_df.copy()
                
                # Clear attrs because pyarrow might choke on custom non-string attributes 
                # (like time_in_market_pct which is a float)
                df_to_save.attrs = {}
                
                df_to_save.index.name = "Date" if "Date" not in df_to_save.columns else "Index_Date"
                df_to_save.reset_index(inplace=True)
                
                # Ensure all columns are str
                df_to_save.columns = [str(c) for c in df_to_save.columns]
                
                df_to_save.to_parquet(parquet_filepath, engine="pyarrow", index=False)
                saved_files['parquet'] = parquet_filepath
            except Exception as e:
                print(f"Failed to save Parquet artifact: {e} (Ensure pyarrow is installed)")
                
        return saved_files

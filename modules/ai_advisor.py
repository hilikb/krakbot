import openai
import json

class AIAdvisor:
    def __init__(self, api_key=None, local_model=None):
        self.api_key = api_key
        self.local_model = local_model

    def format_simulation_summary(self, sim_results: dict) -> str:
        # טיפול במקרה ש־trade_log חסר או ריק
        trades_df = sim_results.get("trade_log", None)
        if trades_df is None or trades_df.empty:
            trades = []
            trade_count = 0
        else:
            trades = trades_df.to_dict(orient="records")
            trade_count = len(trades)

        stats = {
            "Final Balance": round(sim_results.get("final_balance", 0), 2),
            "Total Profit (%)": round(sim_results.get("total_profit_pct", 0) * 100, 2),
            "Trades Executed": trade_count,
        }
        summary = f"Simulation Summary: {json.dumps(stats)}\nSample Trades:\n{json.dumps(trades[:3], indent=2)}"
        return summary

    def ask_for_advice(self, sim_results, strategy_name: str = "combined", mode: str = "long"):
        prompt = f"""
היי, ביצעתי סימולציית מסחר ב־{mode.upper()} עם אסטרטגיה בשם "{strategy_name}".
האם תוכל לנתח את התוצאות ולהציע שיפור באסטרטגיה או שינוי פרמטרים?
הנה הסיכום:

{self.format_simulation_summary(sim_results)}
        """

        if self.api_key:
            return self.ask_chatgpt(prompt)
        elif self.local_model:
            return self.ask_local_model(prompt)
        else:
            return "❌ אין חיבור למודל AI מוגדר."

    def ask_chatgpt(self, prompt: str) -> str:
        try:
            openai.api_key = self.api_key
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "אתה יועץ מסחר מקצועי לקריפטו. הסבר בצורה ברורה, מקצועית וישירה."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response['choices'][0]['message']['content']
        except Exception as e:
            return f"❌ שגיאה בשליחה ל־ChatGPT: {str(e)}"

    def ask_local_model(self, prompt: str) -> str:
        # בעתיד: התחברות ל־ollama / LM Studio / מודל עצמי
        return f"[מודול לוקאלי]: קיבלתי את הבקשה, אך איני מחובר כרגע."

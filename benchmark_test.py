import requests
import pandas as pd
from time import sleep
from pathlib import Path

class DorisRAGBenchmark:
    def __init__(self):
        self.base_url = "http://www.freeoneplus.com:8000/api/ask"
        self.input_file = "/Users/suyijia/Desktop/Doris_RAG_BenchMark.txt"
        self.output_file = Path(__file__).parent / "benchmark_results.xlsx"
        self.results = []
    
    def _format_answer(self, answer: str) -> str:
        """格式化答案中的换行符"""
        return '\n'.join([line.strip() for line in answer.split('\n') if line.strip()])

    def _call_api(self, question: str) -> str:
        """调用问答接口"""
        try:
            response = requests.post(
                self.base_url,
                json={"question": question},
                headers={"Content-Type": "application/json"},
                timeout=120  # 适当延长超时时间
            )
            response.raise_for_status()
            return self._format_answer(response.json()['data'])
        except Exception as e:
            print(f"接口调用失败: {str(e)}")
            return f"错误: {str(e)}"

    def run(self):
        """执行测试流程"""
        # 读取问题列表
        try:
            with open(self.input_file, 'r', encoding='utf-16-le') as f:
                questions = [q.strip() for q in f.readlines() if q.strip()]
        except FileNotFoundError:
            print(f"问题文件未找到: {self.input_file}")
            return

        # 遍历问题并获取答案
        for idx, question in enumerate(questions, 1):
            print(f"正在处理第 {idx}/{len(questions)} 个问题...")
            answer = self._call_api(question)
            self.results.append({
                "序号": idx,
                "问题内容": question,
                "问题答案": answer
            })
            sleep(1)  # 避免频繁调用

        # 保存结果到Excel
        df = pd.DataFrame(self.results)
        df.to_excel(
            self.output_file,
            index=False,
            engine='openpyxl',
            columns=["序号", "问题内容", "问题答案"],
            encoding='utf-8-sig'
        )
        print(f"测试完成，结果已保存至: {self.output_file}")

if __name__ == "__main__":
    benchmark = DorisRAGBenchmark()
    benchmark.run() 
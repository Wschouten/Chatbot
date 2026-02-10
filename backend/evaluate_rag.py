"""RAG Evaluation Framework for GroundCover Chatbot.

This script evaluates the RAG engine's performance across multiple dimensions:
- Keyword matching accuracy
- LLM-as-judge semantic quality ratings
- Hallucination detection for unknown queries
- Response latency tracking
"""
import json
import os
import time
import uuid
from typing import Any

from openai import OpenAI

from rag_engine import RagEngine


class RAGEvaluator:
    """Evaluates RAG engine performance using multiple metrics."""

    def __init__(self, test_set_path: str = "evaluation/test_set.json") -> None:
        """Initialize the evaluator.

        Args:
            test_set_path: Path to the test set JSON file
        """
        self.test_set_path = test_set_path
        self.rag_engine = RagEngine()
        self.openai_client = OpenAI()
        self.chat_model = os.getenv('OPENAI_CHAT_MODEL', 'gpt-5.2')
        self.results: list[dict[str, Any]] = []

    def load_test_set(self) -> list[dict[str, Any]]:
        """Load test questions from JSON file.

        Returns:
            List of test cases with questions, keywords, and metadata
        """
        with open(self.test_set_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def calculate_keyword_score(self, answer: str, keywords: list[str]) -> float:
        """Calculate keyword matching score.

        Performs case-insensitive matching and returns the ratio of
        found keywords to total keywords.

        Args:
            answer: The RAG engine's response
            keywords: List of expected keywords

        Returns:
            Score between 0.0 and 1.0
        """
        if not keywords:
            return 1.0  # No keywords to check

        answer_lower = answer.lower()
        hits = sum(1 for keyword in keywords if keyword.lower() in answer_lower)
        return hits / len(keywords)

    def evaluate_with_llm(self, question: str, answer: str, keywords: list[str]) -> dict[str, Any]:
        """Evaluate answer quality using LLM-as-judge.

        Uses OpenAI to rate the semantic accuracy and helpfulness of the answer
        on a scale of 1-5.

        Args:
            question: The user's question
            answer: The RAG engine's response
            keywords: Expected keywords for context

        Returns:
            Dict with 'score' (1-5) and 'reasoning' (explanation)
        """
        # Skip LLM evaluation for unknown answers
        if "__UNKNOWN__" in answer:
            return {"score": 0, "reasoning": "Answer marked as unknown"}

        keywords_str = ", ".join(keywords) if keywords else "N/A"

        prompt = f"""You are evaluating a chatbot's answer quality.

Question: {question}

Answer: {answer}

Expected topics/keywords: {keywords_str}

Rate the answer on a scale of 1-5:
1 = Completely wrong or irrelevant
2 = Partially correct but missing key information
3 = Adequate but could be more complete
4 = Good answer covering main points
5 = Excellent, comprehensive and helpful

Provide your rating as a JSON object with:
- "score": integer 1-5
- "reasoning": brief explanation (1-2 sentences)

Output only valid JSON, nothing else."""

        try:
            response = self.openai_client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": "You are an expert evaluator. Output only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_completion_tokens=200
            )

            result_text = response.choices[0].message.content
            if result_text:
                result = json.loads(result_text.strip())
                return {
                    "score": result.get("score", 0),
                    "reasoning": result.get("reasoning", "")
                }
        except Exception as e:
            print(f"    Warning: LLM evaluation failed: {e}")
            return {"score": 0, "reasoning": f"Evaluation error: {e}"}

        return {"score": 0, "reasoning": "Failed to parse LLM response"}

    def check_hallucination(self, answer: str, expect_unknown: bool) -> bool:
        """Check if hallucination detection is working correctly.

        For questions where we expect the answer to be unknown, verify that
        the RAG engine correctly returns __UNKNOWN__.

        Args:
            answer: The RAG engine's response
            expect_unknown: Whether we expect __UNKNOWN__ in the answer

        Returns:
            True if hallucination check passed, False otherwise
        """
        has_unknown = "__UNKNOWN__" in answer
        return has_unknown == expect_unknown

    def evaluate_single_question(self, test_case: dict[str, Any]) -> dict[str, Any]:
        """Evaluate a single test question.

        Args:
            test_case: Dict with 'question', 'expected_answer_keywords',
                      'category', and 'expect_unknown'

        Returns:
            Dict with evaluation results including scores, timings, and metadata
        """
        question = test_case["question"]
        keywords = test_case["expected_answer_keywords"]
        category = test_case["category"]
        expect_unknown = test_case["expect_unknown"]

        print(f"  Testing: {question[:60]}...")

        # Generate a temporary session ID for this evaluation
        session_id = str(uuid.uuid4())

        # Measure response time
        start_time = time.time()
        try:
            answer = self.rag_engine.get_answer(question, chat_history=None)
        except Exception as e:
            print(f"    Error: {e}")
            answer = f"ERROR: {e}"
        latency = time.time() - start_time

        # Calculate metrics
        keyword_score = self.calculate_keyword_score(answer, keywords)
        hallucination_pass = self.check_hallucination(answer, expect_unknown)

        # LLM-as-judge evaluation (skip for hallucination checks)
        if expect_unknown:
            llm_eval = {"score": 5 if hallucination_pass else 1, "reasoning": "Hallucination check"}
        else:
            llm_eval = self.evaluate_with_llm(question, answer, keywords)

        result = {
            "question": question,
            "answer": answer,
            "category": category,
            "expect_unknown": expect_unknown,
            "keyword_score": round(keyword_score, 2),
            "llm_score": llm_eval["score"],
            "llm_reasoning": llm_eval["reasoning"],
            "hallucination_pass": hallucination_pass,
            "latency_seconds": round(latency, 2),
            "passed": (
                (hallucination_pass) and
                (llm_eval["score"] >= 3 or expect_unknown)
            )
        }

        print(f"    Keyword: {keyword_score:.2f} | LLM: {llm_eval['score']}/5 | "
              f"Hallucination: {'✓' if hallucination_pass else '✗'} | "
              f"Latency: {latency:.2f}s")

        return result

    def generate_category_breakdown(self) -> dict[str, dict[str, Any]]:
        """Generate performance breakdown by category.

        Returns:
            Dict mapping category names to aggregated metrics
        """
        categories: dict[str, list[dict[str, Any]]] = {}

        for result in self.results:
            cat = result["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(result)

        breakdown = {}
        for cat, results in categories.items():
            total = len(results)
            passed = sum(1 for r in results if r["passed"])
            avg_latency = sum(r["latency_seconds"] for r in results) / total
            avg_keyword = sum(r["keyword_score"] for r in results) / total
            avg_llm = sum(r["llm_score"] for r in results) / total

            breakdown[cat] = {
                "total_questions": total,
                "passed": passed,
                "pass_rate": round(passed / total, 2),
                "avg_latency_seconds": round(avg_latency, 2),
                "avg_keyword_score": round(avg_keyword, 2),
                "avg_llm_score": round(avg_llm, 1)
            }

        return breakdown

    def generate_markdown_report(self, category_breakdown: dict[str, dict[str, Any]]) -> str:
        """Generate human-readable markdown report.

        Args:
            category_breakdown: Aggregated metrics by category

        Returns:
            Markdown-formatted report string
        """
        total_questions = len(self.results)
        total_passed = sum(1 for r in self.results if r["passed"])
        overall_pass_rate = total_passed / total_questions if total_questions > 0 else 0
        avg_latency = sum(r["latency_seconds"] for r in self.results) / total_questions

        report = "# RAG Evaluation Report\n\n"
        report += f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        report += "## Overall Performance\n\n"
        report += f"- **Total Questions:** {total_questions}\n"
        report += f"- **Passed:** {total_passed}\n"
        report += f"- **Pass Rate:** {overall_pass_rate:.1%}\n"
        report += f"- **Average Latency:** {avg_latency:.2f}s\n\n"

        report += "## Performance by Category\n\n"
        report += "| Category | Questions | Pass Rate | Avg Latency | Avg Keyword Score | Avg LLM Score |\n"
        report += "|----------|-----------|-----------|-------------|-------------------|---------------|\n"

        for cat, metrics in sorted(category_breakdown.items()):
            report += (
                f"| {cat} | {metrics['total_questions']} | "
                f"{metrics['pass_rate']:.1%} | {metrics['avg_latency_seconds']:.2f}s | "
                f"{metrics['avg_keyword_score']:.2f} | {metrics['avg_llm_score']:.1f}/5 |\n"
            )

        report += "\n## Detailed Results\n\n"

        # Group by category for detailed view
        by_category: dict[str, list[dict[str, Any]]] = {}
        for result in self.results:
            cat = result["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(result)

        for cat in sorted(by_category.keys()):
            report += f"\n### {cat}\n\n"
            for i, result in enumerate(by_category[cat], 1):
                status = "✓ PASS" if result["passed"] else "✗ FAIL"
                report += f"**{i}. {status}** - {result['question']}\n\n"

                # Show answer preview (truncated)
                answer_preview = result['answer'][:200]
                if len(result['answer']) > 200:
                    answer_preview += "..."
                report += f"- **Answer:** {answer_preview}\n"

                report += f"- **Keyword Score:** {result['keyword_score']:.2f}\n"
                report += f"- **LLM Score:** {result['llm_score']}/5 - {result['llm_reasoning']}\n"
                report += f"- **Hallucination Check:** {'✓ Pass' if result['hallucination_pass'] else '✗ Fail'}\n"
                report += f"- **Latency:** {result['latency_seconds']:.2f}s\n\n"

        report += "\n## Recommendations\n\n"

        if overall_pass_rate < 0.7:
            report += "- **Overall pass rate is below 70%.** Consider:\n"
            report += "  - Reviewing knowledge base content coverage\n"
            report += "  - Adjusting RAG retrieval parameters\n"
            report += "  - Improving system prompts\n\n"

        if avg_latency > 5.0:
            report += "- **Average latency exceeds 5 seconds.** Consider:\n"
            report += "  - Optimizing embedding retrieval\n"
            report += "  - Using a faster LLM model\n"
            report += "  - Reducing chunk sizes\n\n"

        # Category-specific recommendations
        for cat, metrics in category_breakdown.items():
            if metrics["pass_rate"] < 0.7:
                report += f"- **{cat} category performing poorly ({metrics['pass_rate']:.1%} pass rate).**\n"
                report += f"  - Review knowledge base coverage for this category\n\n"

        return report

    def save_results(self, category_breakdown: dict[str, dict[str, Any]]) -> None:
        """Save evaluation results to JSON and markdown files.

        Args:
            category_breakdown: Aggregated metrics by category
        """
        output_dir = "evaluation"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Save JSON results
        json_output = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "summary": {
                "total_questions": len(self.results),
                "passed": sum(1 for r in self.results if r["passed"]),
                "pass_rate": round(
                    sum(1 for r in self.results if r["passed"]) / len(self.results), 3
                ) if self.results else 0,
                "avg_latency_seconds": round(
                    sum(r["latency_seconds"] for r in self.results) / len(self.results), 2
                ) if self.results else 0
            },
            "category_breakdown": category_breakdown,
            "detailed_results": self.results
        }

        json_path = os.path.join(output_dir, "evaluation_results.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_output, f, indent=2, ensure_ascii=False)
        print(f"\nJSON results saved to: {json_path}")

        # Save markdown report
        markdown_report = self.generate_markdown_report(category_breakdown)
        md_path = os.path.join(output_dir, "evaluation_report.md")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_report)
        print(f"Markdown report saved to: {md_path}")

    def run_evaluation(self) -> None:
        """Run the complete evaluation pipeline."""
        print("=" * 70)
        print("RAG Evaluation Framework - GroundCover Chatbot")
        print("=" * 70)
        print()

        # Initialize RAG engine
        print("Initializing RAG engine...")
        print(f"  Chat model: {self.chat_model}")
        print(f"  Embedding model: {self.rag_engine.embedding_model}")
        print()

        # Load test set
        print(f"Loading test set from: {self.test_set_path}")
        test_cases = self.load_test_set()
        print(f"  Loaded {len(test_cases)} test questions")
        print()

        # Count categories
        categories = {}
        for tc in test_cases:
            cat = tc["category"]
            categories[cat] = categories.get(cat, 0) + 1

        print("Test set breakdown:")
        for cat, count in sorted(categories.items()):
            print(f"  - {cat}: {count} questions")
        print()

        # Run evaluation
        print("Running evaluation...")
        print()

        for i, test_case in enumerate(test_cases, 1):
            category = test_case["category"]
            print(f"[{i}/{len(test_cases)}] Category: {category}")

            result = self.evaluate_single_question(test_case)
            self.results.append(result)
            print()

        # Generate category breakdown
        print("Generating category breakdown...")
        category_breakdown = self.generate_category_breakdown()
        print()

        # Display summary
        print("=" * 70)
        print("EVALUATION SUMMARY")
        print("=" * 70)
        print()

        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        pass_rate = passed / total if total > 0 else 0
        avg_latency = sum(r["latency_seconds"] for r in self.results) / total

        print(f"Total Questions:  {total}")
        print(f"Passed:           {passed}")
        print(f"Pass Rate:        {pass_rate:.1%}")
        print(f"Average Latency:  {avg_latency:.2f}s")
        print()

        print("Category Breakdown:")
        print()
        for cat, metrics in sorted(category_breakdown.items()):
            print(f"  {cat}:")
            print(f"    Questions:    {metrics['total_questions']}")
            print(f"    Pass Rate:    {metrics['pass_rate']:.1%}")
            print(f"    Avg Latency:  {metrics['avg_latency_seconds']:.2f}s")
            print(f"    Avg Keyword:  {metrics['avg_keyword_score']:.2f}")
            print(f"    Avg LLM:      {metrics['avg_llm_score']:.1f}/5")
            print()

        # Save results
        self.save_results(category_breakdown)

        print()
        print("=" * 70)
        print("Evaluation complete!")
        print("=" * 70)


if __name__ == "__main__":
    evaluator = RAGEvaluator()
    evaluator.run_evaluation()

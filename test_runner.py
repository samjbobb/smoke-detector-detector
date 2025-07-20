#!/usr/bin/env python3
"""
Test runner for smoke detector validation.
Processes all test cases and reports accuracy metrics.
"""

import json
import sys
import librosa
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
from smoke_detection_algorithm import SmokeAlarmDetector


class TestRunner:
    def __init__(self, test_dir: str = "test_audio"):
        self.test_dir = Path(test_dir)
        self.config_file = self.test_dir / "test_cases.json"
        self.detector = SmokeAlarmDetector()
    
    def load_test_cases(self) -> List[Dict]:
        """Load test case configuration."""
        if not self.config_file.exists():
            print("❌ No test cases found. Run extract_test_audio.py first.")
            return []
        
        with open(self.config_file) as f:
            config = json.load(f)
        
        return [case for case in config["test_cases"] if case["extracted"]]
    
    def run_single_test(self, test_name_or_index: str) -> Dict:
        """Run a single test case with detailed analysis."""
        test_cases = self.load_test_cases()
        
        if not test_cases:
            print("No extracted test cases to run.")
            return {}
        
        # Find test case by name or index
        target_case = None
        if test_name_or_index.isdigit():
            index = int(test_name_or_index) - 1
            if 0 <= index < len(test_cases):
                target_case = test_cases[index]
        else:
            # Search by filename or description
            for case in test_cases:
                if (test_name_or_index.lower() in case["description"].lower() or 
                    test_name_or_index.lower() in case["filename"].lower()):
                    target_case = case
                    break
        
        if not target_case:
            print(f"❌ Test case not found: {test_name_or_index}")
            print("Available test cases:")
            for i, case in enumerate(test_cases, 1):
                print(f"   {i}. {case['description']} ({case['filename']})")
            return {}
        
        print(f"🧪 Running detailed analysis: {target_case['description']}")
        print("=" * 60)
        
        audio_file = self.test_dir / target_case["filename"]
        if not audio_file.exists():
            print(f"   ❌ Audio file not found: {audio_file}")
            return {}
        
        # Run detection
        print(f"🎵 Processing audio file: {target_case['filename']}")
        detections = self._process_audio_file(audio_file, verbose=True)
        expected_alarms = target_case.get("expected_alarms", [])
        
        # Detailed analysis
        result = self._analyze_results(detections, expected_alarms, target_case)
        
        # Print detailed breakdown
        self._print_detailed_analysis(result, detections, expected_alarms)
        
        return result
    
    def run_all_tests(self) -> Dict:
        """Run all test cases and return results."""
        test_cases = self.load_test_cases()
        
        if not test_cases:
            print("No extracted test cases to run.")
            return {"total": 0, "results": []}
        
        print(f"🧪 Running {len(test_cases)} test cases...")
        print("=" * 60)
        
        results = []
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n[{i}/{len(test_cases)}] {test_case['description']}")
            
            audio_file = self.test_dir / test_case["filename"]
            if not audio_file.exists():
                print(f"   ❌ Audio file not found: {audio_file}")
                continue
            
            # Run detection
            detections = self._process_audio_file(audio_file, verbose=False)
            expected_alarms = test_case.get("expected_alarms", [])
            
            # Analyze results
            analysis = self._analyze_results(detections, expected_alarms, test_case)
            results.append(analysis)
            
            # Print summary
            self._print_test_summary(analysis)
        
        # Print overall summary
        self._print_overall_summary(results)
        
        return {"total": len(results), "results": results}
    
    def _process_audio_file(self, audio_file: Path, verbose: bool = True) -> List[Dict]:
        """Process an audio file by streaming chunks to detector."""
        if verbose:
            print(f"   Loading audio file...")
        
        # Load audio file
        try:
            audio_data, sr = librosa.load(audio_file, sr=self.detector.sample_rate, mono=True)
        except Exception as e:
            print(f"   ❌ Error loading audio file: {e}")
            return []
        
        # Reset detection state
        self.detector.reset_state()
        detections = []
        
        # Set up detection callback to collect results
        def collect_detection(detection: Dict) -> None:
            detections.append(detection)
        
        self.detector.set_detection_callback(collect_detection)
        
        # Process audio in chunks
        chunk_samples = self.detector.chunk_size
        total_chunks = len(audio_data) // chunk_samples
        
        if verbose:
            print(f"   Duration: {len(audio_data) / sr:.1f}s")
            print(f"   Processing {total_chunks} chunks...")
        
        for i in range(0, len(audio_data) - chunk_samples, chunk_samples):
            chunk = audio_data[i:i + chunk_samples]
            chunk_start_time = i / sr
            
            # Stream chunk to detector - same method as live monitoring
            self.detector.process_audio_stream(chunk, chunk_start_time)
        
        if verbose:
            if detections:
                print(f"   ✅ Found {len(detections)} smoke alarm detections:")
                for i, detection in enumerate(detections, 1):
                    print(f"      {i}. {detection['timestamp']:.1f}s")
            else:
                print(f"   ℹ️  No smoke alarms detected")
        
        return detections
    
    def _print_detailed_analysis(self, result: Dict, detections: List[Dict], expected: List[float]):
        """Print detailed breakdown of detection results."""
        print(f"\n📊 DETAILED ANALYSIS")
        print("=" * 50)
        
        tolerance = 2.0
        detected_times = [d["timestamp"] for d in detections]
        
        print(f"Expected Alarms ({len(expected)}):")
        if expected:
            for i, exp_time in enumerate(expected, 1):
                print(f"   {i}. {exp_time:.1f}s")
        else:
            print("   (none)")
        
        print(f"\nDetected Alarms ({len(detected_times)}):")
        if detected_times:
            for i, det_time in enumerate(detected_times, 1):
                print(f"   {i}. {det_time:.1f}s")
        else:
            print("   (none)")
        
        print(f"\nClassification (±{tolerance}s tolerance):")
        print("-" * 30)
        
        # Track matches
        matched_expected = set()
        matched_detected = set()
        
        # True Positives - detections that match expected alarms
        print("✅ TRUE POSITIVES:")
        tp_count = 0
        for i, expected_time in enumerate(expected):
            for j, detected_time in enumerate(detected_times):
                if j in matched_detected:
                    continue
                    
                if abs(detected_time - expected_time) <= tolerance:
                    latency = detected_time - expected_time
                    print(f"   Expected {expected_time:.1f}s → Detected {detected_time:.1f}s (latency: {latency:+.1f}s)")
                    matched_expected.add(i)
                    matched_detected.add(j)
                    tp_count += 1
                    break
        
        if tp_count == 0:
            print("   (none)")
        
        # False Negatives - expected alarms that weren't detected
        print(f"\n❌ FALSE NEGATIVES:")
        fn_alarms = [expected[i] for i in range(len(expected)) if i not in matched_expected]
        if fn_alarms:
            for alarm_time in fn_alarms:
                print(f"   Expected {alarm_time:.1f}s → NOT DETECTED")
        else:
            print("   (none)")
        
        # False Positives - detections that don't match any expected alarm
        print(f"\n⚠️  FALSE POSITIVES:")
        fp_detections = [detected_times[j] for j in range(len(detected_times)) if j not in matched_detected]
        if fp_detections:
            for det_time in fp_detections:
                print(f"   Detected {det_time:.1f}s → NO EXPECTED ALARM")
        else:
            print("   (none)")
        
        # Summary
        print(f"\n📈 SUMMARY:")
        print(f"   Precision: {result['precision']:.3f}")
        print(f"   Recall: {result['recall']:.3f}")
        print(f"   F1 Score: {result['f1_score']:.3f}")
        
        if result['avg_latency'] is not None:
            print(f"   Average Latency: {result['avg_latency']:+.2f}s")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        if result['false_positives'] > result['true_positives']:
            print("   • High false positive rate - consider tightening detection thresholds")
        if result['false_negatives'] > 0:
            print("   • Missing alarms - consider lowering detection thresholds or adjusting frequency range")
        if result['f1_score'] < 0.8:
            print("   • Overall performance needs improvement - review algorithm parameters")
        if result['f1_score'] >= 0.9:
            print("   • Excellent performance! 🎉")
    
    def _analyze_results(self, detections: List[Dict], expected: List[float], test_case: Dict) -> Dict:
        """Analyze detection results vs expected alarms."""
        detected_times = [d["timestamp"] for d in detections]
        
        # Match detections to expected alarms (within tolerance)
        tolerance = 2.0  # seconds
        true_positives = 0
        matched_expected = set()
        matched_detected = set()
        
        for i, expected_time in enumerate(expected):
            for j, detected_time in enumerate(detected_times):
                if j in matched_detected:
                    continue
                    
                if abs(detected_time - expected_time) <= tolerance:
                    true_positives += 1
                    matched_expected.add(i)
                    matched_detected.add(j)
                    break
        
        false_positives = len(detections) - true_positives
        false_negatives = len(expected) - true_positives
        
        # Calculate metrics
        # For true negative cases (no expected, no detected), precision and recall are perfect
        if len(expected) == 0 and len(detections) == 0:
            precision = 1.0
            recall = 1.0 
            f1 = 1.0
        else:
            precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
            recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        # Calculate detection latency for matched alarms
        latencies = []
        for i, expected_time in enumerate(expected):
            if i in matched_expected:
                best_match = min(detected_times, key=lambda x: abs(x - expected_time))
                latency = best_match - expected_time
                latencies.append(latency)
        
        avg_latency = sum(latencies) / len(latencies) if latencies else None
        
        return {
            "test_case": test_case["description"],
            "filename": test_case["filename"],
            "duration": test_case["duration"],
            "expected_count": len(expected),
            "detected_count": len(detections),
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "avg_latency": avg_latency,
            "expected_times": expected,
            "detected_times": detected_times,
            "success": f1 > 0.8  # Consider success if F1 > 0.8
        }
    
    def _print_test_summary(self, result: Dict):
        """Print summary for a single test case."""
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        
        print(f"   {status}")
        print(f"   Expected: {result['expected_count']} alarms")
        print(f"   Detected: {result['detected_count']} alarms")
        print(f"   Precision: {result['precision']:.2f}")
        print(f"   Recall: {result['recall']:.2f}")
        print(f"   F1 Score: {result['f1_score']:.2f}")
        
        if result['avg_latency'] is not None:
            print(f"   Avg Latency: {result['avg_latency']:.2f}s")
        
        if result['false_positives'] > 0:
            print(f"   ⚠️  {result['false_positives']} false positive(s)")
        
        if result['false_negatives'] > 0:
            print(f"   ⚠️  {result['false_negatives']} missed alarm(s)")
    
    def _print_overall_summary(self, results: List[Dict]):
        """Print overall test summary."""
        if not results:
            return
        
        print("\n" + "=" * 60)
        print("📊 OVERALL TEST RESULTS")
        print("=" * 60)
        
        passed = sum(1 for r in results if r["success"])
        total = len(results)
        
        avg_precision = sum(r["precision"] for r in results) / total
        avg_recall = sum(r["recall"] for r in results) / total
        avg_f1 = sum(r["f1_score"] for r in results) / total
        
        total_tp = sum(r["true_positives"] for r in results)
        total_fp = sum(r["false_positives"] for r in results)
        total_fn = sum(r["false_negatives"] for r in results)
        
        latencies = [r["avg_latency"] for r in results if r["avg_latency"] is not None]
        avg_latency = sum(latencies) / len(latencies) if latencies else None
        
        print(f"Test Cases: {passed}/{total} passed ({passed/total*100:.1f}%)")
        print(f"Average Precision: {avg_precision:.3f}")
        print(f"Average Recall: {avg_recall:.3f}")
        print(f"Average F1 Score: {avg_f1:.3f}")
        print(f"Total True Positives: {total_tp}")
        print(f"Total False Positives: {total_fp}")
        print(f"Total False Negatives: {total_fn}")
        
        if avg_latency is not None:
            print(f"Average Detection Latency: {avg_latency:.2f}s")
        
        print("\n📈 Performance Assessment:")
        if avg_f1 >= 0.9:
            print("🎉 Excellent performance!")
        elif avg_f1 >= 0.8:
            print("✅ Good performance")
        elif avg_f1 >= 0.6:
            print("⚠️  Acceptable performance - consider tuning")
        else:
            print("❌ Poor performance - needs significant improvement")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Run smoke detector tests")
    parser.add_argument("--test-dir", type=Path, default="test_audio", help="Test directory")
    parser.add_argument("--single", type=str, help="Run single test case by name/description or index number")
    
    args = parser.parse_args()
    
    runner = TestRunner(str(args.test_dir))
    
    if args.single:
        runner.run_single_test(args.single)
    else:
        runner.run_all_tests()


if __name__ == "__main__":
    main()
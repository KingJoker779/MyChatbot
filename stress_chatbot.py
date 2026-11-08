import argparse
from io import StringIO
import sys
import time
import unittest

from test_chatbot import ChatbotRegressionTests


def main():
	parser = argparse.ArgumentParser(description="Repeated chatbot regression/stress tests.")
	parser.add_argument("--minutes", type=float, default=30)
	args = parser.parse_args()
	if not 0 < args.minutes <= 24 * 60:
		parser.error("--minutes must be greater than 0 and no more than 1440")

	started = time.monotonic()
	deadline = started + args.minutes * 60
	cycles = 0
	checks = 0
	last_report = time.monotonic()
	while time.monotonic() < deadline:
		output = StringIO()
		test_suite = unittest.defaultTestLoader.loadTestsFromTestCase(
			ChatbotRegressionTests
		)
		result = unittest.TextTestRunner(stream=output, verbosity=0).run(test_suite)
		cycles += 1
		checks += result.testsRun
		if not result.wasSuccessful():
			print(output.getvalue(), flush=True)
			return 1
		now = time.monotonic()
		if now - last_report >= 30:
			print(
				f"{(now - started) / 60:.1f} minutes: "
				f"{cycles:,} clean cycles, {checks:,} checks",
				flush=True,
			)
			last_report = now

	print(
		f"PASS: {args.minutes:g}-minute stress run; "
		f"{cycles:,} clean cycles, {checks:,} checks.",
		flush=True,
	)
	return 0


if __name__ == "__main__":
	sys.exit(main())

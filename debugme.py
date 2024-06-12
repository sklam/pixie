import os

os.environ["CLANG"] = "/Users/siu/miniconda3-arm64/envs/pixie.py311/bin/clang"
import unittest
import types

# Assuming 'test_module_name' is the name of your test module
# test_module_name = 'pixie.tests.test_selectors.TestSelectors.test_pyversion_selector'
test_module_name = 'pixie.tests.test_selectors.TestSelectors.test_arm64_isa_selector'

# Load the test module
loaded_tests = unittest.defaultTestLoader.loadTestsFromName(test_module_name)

# Create a test suite
suite = unittest.TestSuite()
suite.addTests(loaded_tests)

print("-" * 80)
# Run the test suite
runner = unittest.TextTestRunner()
results = runner.run(suite)

# Print the results
print(results)


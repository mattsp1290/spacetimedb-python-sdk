# Makefile for Phase 2 Refactoring Tests
# Provides convenient commands for running different test suites

.PHONY: help install test test-regression test-module test-integration test-performance test-e2e test-fast test-coverage test-memory test-concurrent clean setup lint format check-format

# Default target
help:
	@echo "SpacetimeDB Python SDK - Phase 2 Refactoring Test Suite"
	@echo "========================================================"
	@echo ""
	@echo "Available targets:"
	@echo "  help              Show this help message"
	@echo "  install           Install test dependencies"
	@echo "  setup             Set up test environment"
	@echo "  test              Run all tests"
	@echo "  test-regression   Run regression tests"
	@echo "  test-module       Run module tests"
	@echo "  test-integration  Run integration tests"
	@echo "  test-performance  Run performance tests"
	@echo "  test-e2e          Run end-to-end tests"
	@echo "  test-fast         Run fast tests only"
	@echo "  test-coverage     Run tests with coverage"
	@echo "  test-memory       Run memory tests"
	@echo "  test-concurrent   Run concurrency tests"
	@echo "  lint              Run code linting"
	@echo "  format            Format code"
	@echo "  check-format      Check code formatting"
	@echo "  clean             Clean test artifacts"

# Install test dependencies
install:
	@echo "Installing test dependencies..."
	pip install pytest pytest-cov pytest-mock pytest-timeout pytest-xdist
	pip install psutil  # For memory monitoring
	pip install websocket-client  # For WebSocket mocking

# Set up test environment
setup: install
	@echo "Setting up test environment..."
	mkdir -p coverage_html
	mkdir -p .pytest_cache
	@echo "Test environment ready!"

# Run all tests
test:
	@./run_tests.py --suite all --verbose

# Run regression tests
test-regression:
	@echo "Running regression tests..."
	@./run_tests.py --suite regression --verbose

# Run module tests
test-module:
	@echo "Running module tests..."
	@./run_tests.py --suite module --verbose

# Run integration tests
test-integration:
	@echo "Running integration tests..."
	@./run_tests.py --suite integration --verbose

# Run performance tests
test-performance:
	@echo "Running performance tests..."
	@./run_tests.py --suite performance --verbose

# Run end-to-end tests
test-e2e:
	@echo "Running end-to-end tests..."
	@./run_tests.py --suite end-to-end --verbose

# Run fast tests only
test-fast:
	@echo "Running fast tests..."
	@./run_tests.py --suite fast --verbose

# Run tests with coverage
test-coverage:
	@echo "Running tests with coverage analysis..."
	@./run_tests.py --suite coverage
	@echo "Coverage report generated in coverage_html/"

# Run memory tests
test-memory:
	@echo "Running memory tests..."
	@./run_tests.py --suite memory --verbose

# Run concurrency tests
test-concurrent:
	@echo "Running concurrency tests..."
	@./run_tests.py --suite concurrent --verbose

# Run tests in parallel
test-parallel:
	@echo "Running tests in parallel..."
	@./run_tests.py --suite all --parallel --verbose

# Generate comprehensive test report
test-report:
	@echo "Generating comprehensive test report..."
	@./run_tests.py --suite all --report test_report.json
	@echo "Test report saved to test_report.json"

# Lint code
lint:
	@echo "Running code linting..."
	python -m flake8 . --max-line-length=120 --ignore=E501,W503
	python -m pylint *.py --disable=C0114,C0115,C0116

# Format code
format:
	@echo "Formatting code..."
	python -m black . --line-length=120
	python -m isort . --profile black

# Check code formatting
check-format:
	@echo "Checking code formatting..."
	python -m black . --check --line-length=120
	python -m isort . --check-only --profile black

# Clean test artifacts
clean:
	@echo "Cleaning test artifacts..."
	rm -rf .pytest_cache/
	rm -rf coverage_html/
	rm -rf __pycache__/
	rm -rf *.pyc
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf test_results.xml
	rm -rf test_report.json
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +
	@echo "Clean complete!"

# Run specific test file
test-file:
	@if [ -z "$(FILE)" ]; then \
		echo "Usage: make test-file FILE=test_filename.py"; \
	else \
		echo "Running $(FILE)..."; \
		python -m pytest $(FILE) -v; \
	fi

# Run tests with specific marker
test-marker:
	@if [ -z "$(MARKER)" ]; then \
		echo "Usage: make test-marker MARKER=marker_name"; \
	else \
		echo "Running tests with marker $(MARKER)..."; \
		python -m pytest -m $(MARKER) -v; \
	fi

# Development workflow targets
dev-test: test-fast lint

pre-commit: check-format lint test-fast

ci-test: setup test-coverage

# Performance benchmarking
benchmark:
	@echo "Running performance benchmarks..."
	@./run_tests.py --suite performance --report benchmark_report.json
	@echo "Benchmark results saved to benchmark_report.json"

# Memory profiling
profile-memory:
	@echo "Running memory profiling..."
	python -m pytest test_performance_regression.py::TestPerformanceRegression::test_memory_efficiency_regression --verbose

# Stress testing
stress-test:
	@echo "Running stress tests..."
	@./run_tests.py --markers concurrent memory --verbose

# Validation suite (for pre-merge checks)
validate: setup test-coverage lint check-format
	@echo "✅ Validation complete!"

# Quick development check
quick: test-fast lint
	@echo "✅ Quick check complete!"
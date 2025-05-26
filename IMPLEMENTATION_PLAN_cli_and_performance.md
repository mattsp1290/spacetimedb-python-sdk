# Implementation Plan: CLI Integration & Performance Testing

## Overview
Working on two critical tasks in parallel:
1. **Python CLI Integration (prof-1)**: Making Python a first-class citizen in SpacetimeDB CLI
2. **Performance Testing (ts-parity-19)**: Comprehensive benchmarking and optimization

## Task 1: Python CLI Integration

### Current Status
- ✅ Python code generation fully implemented
- ✅ `spacetime generate --lang python` works
- ✅ Python formatting tools integrated
- ❌ Python not in ModuleLanguage enum
- ❌ No `spacetime init --lang python` support
- ❌ No Python project templates
- ❌ Build system doesn't handle Python

### Implementation Steps

#### Phase 1: Basic CLI Support (Day 1)
1. **Update util.rs**
   - Add Python to ModuleLanguage enum
   - Add Python aliases ["python", "py", "Python"]
   - Update detect_module_language() to detect Python projects

2. **Update init.rs**
   - Add exec_init_python() function
   - Add Python dependency checks (check_for_python())
   - Wire up Python support in exec()

3. **Create Python Templates**
   - `/project/python/pyproject._toml`
   - `/project/python/__init__._py`
   - `/project/python/main._py`
   - `/project/python/_gitignore`
   - `/project/python/requirements._txt`

#### Phase 2: Build Integration (Day 2)
1. **Update tasks/mod.rs**
   - Add Python case to build() function
   - Import build_python from python.rs

2. **Enhance tasks/python.rs**
   - Implement proper Python module building
   - Add validation for Python modules
   - Support Python-specific build options

### Files to Modify
- `/SpacetimeDB/crates/cli/src/util.rs`
- `/SpacetimeDB/crates/cli/src/subcommands/init.rs`
- `/SpacetimeDB/crates/cli/src/tasks/mod.rs`
- `/SpacetimeDB/crates/cli/src/tasks/python.rs`

### Files to Create
- `/SpacetimeDB/crates/cli/src/subcommands/project/python/` (directory)
- Python template files

## Task 2: Performance Testing (ts-parity-19)

### Implementation Steps

#### Phase 1: Benchmark Infrastructure (Day 1)
1. **Create benchmark framework**
   - `test_performance_benchmarks.py`
   - Performance metrics collection
   - Comparison with TypeScript/Go baselines

2. **Core Performance Tests**
   - Operation latency (target: nanosecond precision)
   - Throughput testing (target: >400K ops/sec)
   - Memory usage profiling
   - Connection scalability (1000+ concurrent)

#### Phase 2: Stress Testing (Day 2)
1. **High-volume operations**
   - Million+ record operations
   - Concurrent client simulation (100+ clients)
   - Resource exhaustion scenarios
   - Recovery testing

2. **Production Readiness**
   - Real-world workload simulation
   - Performance regression testing
   - Monitoring integration
   - Optimization recommendations

### Benchmark Categories
1. **BSATN Performance**
   - Serialization/deserialization speed
   - Large object handling
   - Complex type performance

2. **Network Performance**
   - WebSocket message throughput
   - Latency under load
   - Connection establishment time

3. **Client Performance**
   - Table operations (CRUD)
   - Subscription handling
   - Event processing

4. **Memory Performance**
   - Memory usage per connection
   - Garbage collection impact
   - Cache efficiency

### Success Metrics
- Python SDK performance within 10% of TypeScript SDK
- Memory usage optimized for production
- Scalability to 1000+ concurrent connections
- Sub-millisecond operation latency

## Timeline
- Day 1: CLI Phase 1 + Performance Infrastructure
- Day 2: CLI Phase 2 + Stress Testing
- Day 3: Integration testing + Performance optimization
- Day 4: Documentation + Final benchmarks

## Dependencies
- SpacetimeDB repository access
- Python 3.8+ for testing
- Performance profiling tools (cProfile, memory_profiler)
- Load testing tools

## Risks & Mitigation
1. **Risk**: SpacetimeDB API changes
   - **Mitigation**: Work with current stable version, document compatibility

2. **Risk**: Performance regression
   - **Mitigation**: Establish baseline early, continuous monitoring

3. **Risk**: Python module format undefined
   - **Mitigation**: Define minimal viable format for CLI integration

## Success Criteria
1. `spacetime init --lang python` creates working project
2. `spacetime generate --lang python` produces correct client code
3. Python projects auto-detected by CLI
4. Performance benchmarks show production readiness
5. Documentation complete for both features

# Comprehensive Python Code Review Prompt

You are an AI agent specializing in conducting thorough, actionable code reviews for Python projects. Your task is to perform a comprehensive review of the SpacetimeDB Python SDK project, with a particular focus on modernization and architectural improvements.

## Primary Objectives

1. **Conduct a full code review** of the entire codebase
2. **Identify and modernize legacy code** - specifically:
   - Locate all "unified" and "modern" versions of classes/clients
   - Recommend consolidation strategies to make these the primary implementations
   - Remove deprecated/original versions that are no longer used
   - Eliminate "unified" or "modern" monikers from naming conventions
   - Establish these as the canonical way to use each feature

3. **Document findings** in markdown files located at: `/Users/punk1290/git/spacetimedb-python-sdk/proompts/reviews/`
   - Create a new timestamped folder for this review session
   - Organize findings into multiple focused markdown documents

## Review Methodology

### Phase 1: Codebase Analysis
Perform an initial sweep to understand:
- Overall project structure and architecture
- Identify all duplicate implementations (original vs unified/modern versions)
- Map dependencies between components
- Document the current state of the codebase

### Phase 2: Deep Technical Review
Apply the following checklist systematically:

#### Code Quality & Standards
- **PEP 8 Compliance**: Verify adherence to Python style guidelines
- **Type Hints**: Check for consistent use of type annotations
- **Docstrings**: Ensure comprehensive documentation following Google/NumPy style
- **Naming Conventions**: Validate clarity and consistency of names
- **Code Formatting**: Verify consistent use of Black/autopep8 formatting

#### Architecture & Design
- **SOLID Principles**: Evaluate adherence to software design principles
- **Design Patterns**: Ensure appropriate use of design patterns
- **Modularity**: Check for proper separation of concerns
- **Dependencies**: Review import structure and circular dependency risks
- **Abstraction Levels**: Verify appropriate levels of abstraction

#### Best Practices (per https://gist.github.com/ruimaranhao/4e18cbe3dad6f68040c32ed6709090a3)
- **Composition over Inheritance**: Prefer composition patterns
- **Immutability**: Favor immutable data structures where appropriate
- **Comprehensions**: Use list/dict/set comprehensions appropriately
- **Context Managers**: Proper use of `with` statements
- **Exception Handling**: Specific exception catching, no bare excepts
- **Resource Management**: Proper cleanup of resources

#### Security & Performance
- **Input Validation**: Check all user inputs are properly sanitized
- **SQL Injection**: Verify parameterized queries if applicable
- **Performance Bottlenecks**: Identify O(n²) operations, unnecessary loops
- **Memory Management**: Check for memory leaks, large object retention
- **Concurrency**: Review thread safety and async patterns

#### Testing & Reliability
- **Test Coverage**: Evaluate unit test completeness
- **Edge Cases**: Ensure handling of boundary conditions
- **Error Scenarios**: Verify graceful error handling
- **Integration Tests**: Check for proper integration testing
- **Mocking Strategy**: Appropriate use of mocks and fixtures

### Phase 3: Modernization Recommendations

Focus specifically on:
1. **Version Consolidation Plan**
   - Map all original → unified/modern version pairs
   - Create migration strategy for each component
   - Define deprecation timeline
   - Suggest refactoring approach

2. **API Consistency**
   - Ensure consistent interfaces across modernized components
   - Standardize method signatures and return types
   - Align error handling patterns

3. **Breaking Change Management**
   - Document all breaking changes
   - Suggest migration guides for users
   - Propose compatibility layers if needed

## Output Structure

Create the following markdown documents:

### 1. `executive_summary.md`
- High-level findings and recommendations
- Priority action items
- Risk assessment
- Modernization roadmap

### 2. `codebase_analysis.md`
- Current architecture overview
- Component dependency graph
- Technical debt assessment
- Performance bottlenecks

### 3. `modernization_plan.md`
- Detailed mapping of original → modern versions
- Step-by-step consolidation strategy
- Breaking changes documentation
- Migration timeline

### 4. `code_quality_issues.md`
- Style and formatting violations
- Best practice deviations
- Security vulnerabilities
- Performance concerns

### 5. `testing_recommendations.md`
- Current test coverage analysis
- Missing test scenarios
- Testing strategy improvements
- CI/CD enhancements

### 6. `detailed_findings/` (folder)
- Individual markdown files for each major component
- Line-by-line review comments
- Specific code examples and fixes

## Review Guidelines

1. **Be Constructive**: Frame criticism positively with solutions
2. **Prioritize Impact**: Focus on high-impact improvements first
3. **Provide Examples**: Include code snippets showing "before" and "after"
4. **Consider Context**: Understand historical decisions before recommending changes
5. **Balance Perfection with Pragmatism**: Suggest realistic improvements

## Special Considerations

- Pay extra attention to the PDF guide at `/Users/punk1290/Documents/ebooks/Looks_Good_to_Me_.pdf` for PR feedback best practices
- Use "ultrathinking" to deeply analyze architectural decisions
- Consider backward compatibility implications for all recommendations
- Document any assumptions made during the review

## Deliverables Checklist

- [ ] Executive summary with actionable recommendations
- [ ] Complete codebase analysis with visual diagrams where helpful
- [ ] Detailed modernization plan with clear steps
- [ ] Comprehensive list of all code quality issues
- [ ] Testing strategy improvements
- [ ] Component-specific detailed reviews
- [ ] Migration guides for moving from original to modern versions
- [ ] Risk assessment for proposed changes

Remember: The goal is not just to identify issues, but to provide a clear, actionable path forward that will result in a more maintainable, modern, and efficient codebase.

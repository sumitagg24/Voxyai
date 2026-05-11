# Contributing to Voxylis

Thank you for your interest in contributing to Voxylis! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the code, not the person
- Help others learn and grow

## Getting Started

### 1. Fork the Repository
```bash
# Click "Fork" on GitHub
```

### 2. Clone Your Fork
```bash
git clone https://github.com/YOUR_USERNAME/voxylis.git
cd voxylis
```

### 3. Add Upstream Remote
```bash
git remote add upstream https://github.com/ORIGINAL_OWNER/voxylis.git
```

### 4. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 5. Install Dependencies
```bash
pip install -r requirements.txt
pip install pytest pytest-cov black flake8
```

## Development Workflow

### 1. Create Feature Branch
```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes
- Write clean, well-commented code
- Follow PEP 8 style guide
- Add docstrings to functions
- Keep commits atomic and focused

### 3. Test Your Changes
```bash
# Run tests
pytest tests/

# Check code style
flake8 .

# Format code
black .

# Check coverage
pytest --cov=.
```

### 4. Commit Changes
```bash
git add .
git commit -m "feat: add new feature description"
```

### 5. Push to Your Fork
```bash
git push origin feature/your-feature-name
```

### 6. Create Pull Request
- Go to GitHub
- Click "New Pull Request"
- Select your branch
- Fill in description
- Submit PR

## Commit Message Guidelines

### Format
```
<type>: <subject>

<body>

<footer>
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style (formatting)
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `test`: Test addition/modification
- `chore`: Build/dependency changes

### Examples
```
feat: add voice command support

Implement voice command detection and processing
for common actions like email composition.

Closes #123
```

```
fix: resolve text injection failure in VS Code

Handle special clipboard behavior in VS Code
by implementing fallback typing mode.

Fixes #456
```

## Code Style Guidelines

### Python Style
- Follow PEP 8
- Use 4 spaces for indentation
- Maximum line length: 100 characters
- Use type hints where possible

### Example
```python
def enhance_text(text: str, mode: str = "formal") -> Optional[str]:
    """
    Enhance text using AI.
    
    Args:
        text: Raw text to enhance
        mode: Enhancement mode (formal, casual, etc.)
    
    Returns:
        Enhanced text or None if error
    """
    if not text or not text.strip():
        log_warning("Empty text provided")
        return text
    
    try:
        # Implementation
        return enhanced_text
    except Exception as e:
        log_error(f"Enhancement error: {e}", exc_info=True)
        return text
```

### Naming Conventions
- Functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_leading_underscore`

### Documentation
- Add docstrings to all functions
- Use Google-style docstrings
- Include type hints
- Add examples for complex functions

## Testing Guidelines

### Unit Tests
```python
import pytest
from audio.audio_utils import normalize_audio

def test_normalize_audio():
    """Test audio normalization"""
    audio = np.array([1000, 2000, 3000], dtype=np.int16)
    normalized = normalize_audio(audio)
    
    assert np.max(np.abs(normalized)) <= 32767
    assert len(normalized) == len(audio)
```

### Test Coverage
- Aim for 80%+ coverage
- Test happy path and error cases
- Test edge cases
- Use fixtures for common setup

### Running Tests
```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_audio.py::test_normalize_audio

# Run with coverage
pytest --cov=. --cov-report=html
```

## Documentation Guidelines

### README Updates
- Keep README.md current
- Add new features to feature list
- Update troubleshooting section
- Include examples

### Code Comments
- Explain "why", not "what"
- Keep comments concise
- Update comments when code changes
- Use TODO for future work

### Docstrings
```python
def process_audio(audio_data: np.ndarray, mode: str = "enhance") -> Optional[str]:
    """
    Process audio through the enhancement pipeline.
    
    This function handles the complete audio processing workflow:
    1. Transcribe audio to text
    2. Enhance text based on mode
    3. Return enhanced text
    
    Args:
        audio_data: Audio samples as numpy array (int16)
        mode: Processing mode ('enhance', 'transcribe_only', etc.)
    
    Returns:
        Enhanced text string or None if processing failed
    
    Raises:
        ValueError: If audio_data is empty
        RuntimeError: If API call fails
    
    Example:
        >>> audio = np.array([...], dtype=np.int16)
        >>> result = process_audio(audio, mode="enhance")
        >>> print(result)
        "Enhanced text here"
    """
```

## Pull Request Guidelines

### Before Submitting
- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] Code coverage maintained
- [ ] Documentation updated
- [ ] Commit messages are clear
- [ ] No merge conflicts

### PR Description Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Related Issues
Closes #123

## Testing
- [ ] Unit tests added
- [ ] Integration tests passed
- [ ] Manual testing completed

## Screenshots (if applicable)
[Add screenshots here]

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No new warnings generated
```

## Issue Guidelines

### Reporting Bugs
```markdown
## Description
Clear description of the bug

## Steps to Reproduce
1. Step 1
2. Step 2
3. Step 3

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: Windows 10
- Python: 3.9
- Version: 1.0.0

## Logs
[Paste relevant logs]

## Screenshots
[Add screenshots if applicable]
```

### Feature Requests
```markdown
## Description
Clear description of the feature

## Use Case
Why this feature is needed

## Proposed Solution
How it should work

## Alternatives
Other possible approaches

## Additional Context
Any other relevant information
```

## Development Tips

### Debugging
```python
# Add debug logging
from utils.logger import log_debug
log_debug(f"Variable value: {variable}")

# Use breakpoints
import pdb; pdb.set_trace()

# Check logs
tail -f logs/voxylis.log
```

### Performance Profiling
```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Code to profile
process_audio(audio_data)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(10)
```

### Memory Profiling
```bash
pip install memory-profiler
python -m memory_profiler main.py
```

## Release Process

### Version Numbering
- Major.Minor.Patch (e.g., 1.0.0)
- Major: Breaking changes
- Minor: New features
- Patch: Bug fixes

### Release Checklist
- [ ] Update version in code
- [ ] Update CHANGELOG.md
- [ ] Update README.md
- [ ] Run full test suite
- [ ] Create GitHub release
- [ ] Build executable
- [ ] Upload to releases

## Getting Help

- Check existing issues and PRs
- Read documentation
- Ask in discussions
- Contact maintainers

## Recognition

Contributors will be recognized in:
- README.md contributors section
- Release notes
- GitHub contributors page

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Thank you for contributing to Voxylis! 🎉**

# Contributing to MedImageParse

Thank you for your interest in contributing to MedImageParse! This document provides guidelines for contributing to the project.

## Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please be respectful and professional in all interactions.

## How to Contribute

### Reporting Bugs

1. **Search existing issues** to avoid duplicates
2. **Create a new issue** with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Screenshots if applicable
   - Environment details (OS, Python version, etc.)

### Suggesting Features

1. **Check roadmap** in README.md
2. **Open a feature request** with:
   - Use case description
   - Proposed solution
   - Alternative approaches considered
   - Impact assessment

### Contributing Code

#### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/your-org/MedImageParse.git
cd MedImageParse

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r src/requirements.txt
pip install -r requirements-dev.txt  # If exists

# Install pre-commit hooks (if configured)
pre-commit install
```

#### Development Workflow

1. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes**
   - Follow code style guidelines (below)
   - Add tests for new features
   - Update documentation

3. **Test locally**
   ```bash
   # Run unit tests
   pytest tests/unit/
   
   # Run with coverage
   pytest --cov=src tests/
   
   # Test locally
   streamlit run src/app.py
   ```

4. **Commit changes**
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```
   
   Follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` New feature
   - `fix:` Bug fix
   - `docs:` Documentation changes
   - `test:` Test additions/changes
   - `refactor:` Code refactoring
   - `chore:` Maintenance tasks

5. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   
   Then open a Pull Request on GitHub.

#### Code Style Guidelines

**Python**
- Follow [PEP 8](https://pep8.org/)
- Use type hints where applicable
- Maximum line length: 100 characters
- Use docstrings for functions and classes

**Example**:
```python
def process_image(image_path: str, model_type: str = "2D") -> np.ndarray:
    """
    Process medical image using specified model
    
    Args:
        image_path: Path to the image file
        model_type: Type of model to use ("2D" or "3D")
        
    Returns:
        Segmentation mask as numpy array
        
    Raises:
        FileNotFoundError: If image file doesn't exist
        ValueError: If model_type is invalid
    """
    # Implementation
    pass
```

**Bicep/Infrastructure**
- Use descriptive parameter names
- Add comments for complex logic
- Follow Azure naming conventions
- Use modules for reusability

**Documentation**
- Use Markdown for all documentation
- Include code examples where helpful
- Keep language clear and concise
- Update relevant docs when changing features

#### Testing Guidelines

**Unit Tests**
- Test each function/method independently
- Use mocks for external dependencies
- Aim for 80%+ code coverage
- Name tests descriptively: `test_<function>_<scenario>`

**Example**:
```python
def test_decode_nifti_valid_input():
    """Test NIfTI decoding with valid input"""
    # Arrange
    test_data = create_test_nifti()
    
    # Act
    result = decode_base64_to_nifti(test_data)
    
    # Assert
    assert result is not None
    assert result.shape == (256, 256, 128)
```

**Integration Tests**
- Test interactions between components
- Use test fixtures for setup/teardown
- Mock external services (Azure ML endpoints)

#### Pull Request Guidelines

**PR Title**
- Use conventional commit format
- Be clear and descriptive
- Example: `feat: add DICOM format support`

**PR Description**
Include:
- **What**: Summary of changes
- **Why**: Motivation and context
- **How**: Technical approach
- **Testing**: How you tested the changes
- **Screenshots**: If UI changes
- **Breaking Changes**: If any

**PR Template**:
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Tested locally
- [ ] Tested in Azure

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests pass locally

## Related Issues
Fixes #<issue-number>
```

#### Review Process

1. **Automated checks** must pass:
   - Linting
   - Unit tests
   - Build verification

2. **Code review** by maintainer:
   - Code quality
   - Test coverage
   - Documentation completeness

3. **Address feedback**:
   - Make requested changes
   - Push updates to PR branch
   - Re-request review

4. **Merge**:
   - Squash and merge (default)
   - Delete branch after merge

## Project Structure

```
MedImageParse/
├── .github/
│   └── workflows/          # CI/CD pipelines
├── docs/                   # Additional documentation
├── infra/                  # Infrastructure as Code
│   ├── modules/           # Bicep modules
│   └── scripts/           # Deployment scripts
├── src/                   # Application source code
│   ├── app.py            # Main Streamlit app
│   ├── config.py         # Configuration management
│   ├── telemetry.py      # Logging and monitoring
│   └── requirements.txt  # Python dependencies
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── ARCHITECTURE.md        # Architecture documentation
├── README.md             # Project overview
└── CONTRIBUTING.md       # This file
```

## Development Tips

### Local Development with Azure Services

**Use .env file**:
```bash
cp .env.example .env
# Edit .env with your credentials
```

**Mock Azure services**:
```python
# Use environment variables to toggle mocks
if os.getenv('MOCK_AZURE', 'false') == 'true':
    # Use mock implementations
    pass
```

### Debugging Streamlit

```bash
# Run with debug mode
streamlit run src/app.py --logger.level=debug

# Access state in browser console
# Streamlit exposes session state
```

### Testing Bicep Templates

```bash
# Validate syntax
az bicep build --file infra/main.bicep

# What-if deployment (see changes without applying)
az deployment sub what-if \
  --location swedencentral \
  --template-file infra/main.bicep \
  --parameters infra/main.parameters.json
```

### Performance Profiling

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code here

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats()
```

## Documentation Standards

### Code Comments

**When to comment**:
- Complex algorithms
- Non-obvious business logic
- Workarounds for known issues
- TODOs with issue reference

**When NOT to comment**:
- Self-explanatory code
- Obvious variable names
- Restating what code does

### API Documentation

Use docstrings with Google style:

```python
def segment_image(
    image: np.ndarray,
    prompt: str,
    model_type: str = "2D"
) -> Dict[str, Any]:
    """
    Segment medical image using natural language prompt.
    
    This function sends the image to Azure ML endpoint for segmentation
    and returns the segmentation mask along with metadata.
    
    Args:
        image: Input image as numpy array (H, W, C)
        prompt: Natural language description of segmentation target
        model_type: Type of model to use, either "2D" or "3D"
        
    Returns:
        Dictionary containing:
            - mask: Segmentation mask (same size as input)
            - labels: Detected object labels
            - confidence: Confidence scores per object
            
    Raises:
        ValueError: If model_type is not "2D" or "3D"
        RuntimeError: If model inference fails
        
    Example:
        >>> image = load_image("scan.png")
        >>> result = segment_image(image, "liver & kidney")
        >>> mask = result['mask']
    """
    pass
```

## Release Process

### Versioning

We follow [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

### Release Checklist

1. **Update version** in relevant files
2. **Update CHANGELOG.md**
3. **Run full test suite**
4. **Update documentation**
5. **Create release branch**: `release/v1.2.0`
6. **Tag release**: `git tag v1.2.0`
7. **Push tag**: `git push origin v1.2.0`
8. **Create GitHub release** with notes
9. **Deploy to production**

## Getting Help

- **Questions**: Open a Discussion on GitHub
- **Bugs**: Open an Issue
- **Security**: Email security@example.com (do NOT open public issue)
- **Chat**: Join our Discord/Slack (if applicable)

## Recognition

Contributors will be recognized in:
- CONTRIBUTORS.md file
- Release notes
- Project README

## License

By contributing, you agree that your contributions will be licensed under the project's MIT License.

---

Thank you for contributing to MedImageParse! 🎉

**Maintainer**: Xinyuwei
**Last Updated**: October 2025

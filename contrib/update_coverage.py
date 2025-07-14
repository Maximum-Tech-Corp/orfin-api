import re
import subprocess
from pathlib import Path


def get_coverage_stats():
    # Run coverage and capture output
    result = subprocess.run(['coverage', 'report'],
                            capture_output=True, text=True)

    # Get the last line with total coverage
    lines = result.stdout.split('\n')
    total_line = [line for line in lines if 'TOTAL' in line][0]

    # Extract coverage percentage
    coverage = re.search(r'(\d+)%', total_line)
    if coverage is None:
        raise ValueError("Coverage percentage not found in output")
    coverage = coverage.group(1)
    return coverage


def update_readme(coverage):
    readme_path = Path('README.md')
    content = readme_path.read_text()

    # Update or add coverage badge
    coverage_badge = f'![Coverage](https://img.shields.io/badge/coverage-{coverage}%25-{get_badge_color(int(coverage))})'

    if '![Coverage]' in content:
        content = re.sub(r'!\[Coverage\].*', coverage_badge, content)
    else:
        # Add after first heading
        content = re.sub(r'(#[^\n]+\n)', f'\\1\n{coverage_badge}\n', content)

    readme_path.write_text(content)


def get_badge_color(coverage):
    if coverage >= 90:
        return 'brightgreen'
    if coverage >= 75:
        return 'yellow'
    return 'red'


if __name__ == '__main__':
    coverage = get_coverage_stats()
    update_readme(coverage)
    print(f'Updated README.md with {coverage}% coverage')

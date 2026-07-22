"""
McMaker Projects Knowledge Crawler.
Walks the C:\McMaker Projects tree and extracts structured knowledge
for ingestion into Medusa's knowledge base.
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Files that contain high-value project knowledge
KNOWLEDGE_FILES = [
    "README.md", "README", "AGENTS.md", "agents.md",
    "DEPLOY.md", "deploy.md", "PLAN.md", "plan.md",
    "CHANGELOG.md", "TODO.md", "OVERVIEW.md",
    "setup.py", "package.json", "Cargo.toml", "CMakeLists.txt",
    "requirements.txt", "pyproject.toml", "pom.xml",
    ".env.example", "docker-compose.yml", "Dockerfile",
]

# Max content size per file (characters)
MAX_FILE_SIZE = 50000

# Directories to skip
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    ".pytest_cache", ".cache", "build", "dist", "target",
    "obj", "bin", "lib", ".vs", ".idea", ".vscode",
    "logs", "tmp", "temp", "coverage", "htmlcov",
    "site-packages", "egg-info", "node_modules",
}


def should_skip_dir(dir_name: str) -> bool:
    return dir_name in SKIP_DIRS or dir_name.startswith(".")


def is_knowledge_file(filename: str) -> bool:
    return filename in KNOWLEDGE_FILES or any(filename.endswith(ext) for ext in [".md", ".rst", ".txt"])


def read_file_safely(path: Path) -> Optional[str]:
    try:
        size = path.stat().st_size
        if size > MAX_FILE_SIZE:
            return f"[File too large: {size} bytes]"
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        logger.warning(f"Could not read {path}: {e}")
        return None


def extract_project_summary(project_path: Path) -> Dict:
    """Extract a summary of a single project directory."""
    summary = {
        "name": project_path.name,
        "path": str(project_path),
        "files_found": [],
        "knowledge_entries": [],
        "subprojects": [],
        "has_code": False,
        "languages": set(),
    }
    
    code_extensions = {
        ".py": "Python", ".cpp": "C++", ".c": "C", ".hpp": "C++", ".h": "C/C++",
        ".js": "JavaScript", ".ts": "TypeScript", ".jsx": "React", ".tsx": "React",
        ".java": "Java", ".kt": "Kotlin", ".rs": "Rust", ".go": "Go",
        ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".swift": "Swift",
        ".scala": "Scala", ".r": "R", ".m": "MATLAB/Objective-C",
        ".sql": "SQL", ".sh": "Shell", ".ps1": "PowerShell", ".bat": "Batch",
        ".cmake": "CMake", ".make": "Makefile", ".dockerfile": "Docker",
    }
    
    try:
        for item in project_path.iterdir():
            if item.is_dir():
                if not should_skip_dir(item.name):
                    # One level deep for subprojects
                    summary["subprojects"].append(item.name)
            elif item.is_file():
                fname = item.name
                ext = item.suffix.lower()
                
                if is_knowledge_file(fname):
                    content = read_file_safely(item)
                    if content:
                        summary["files_found"].append(fname)
                        summary["knowledge_entries"].append({
                            "file": fname,
                            "content": content[:MAX_FILE_SIZE],
                        })
                
                if ext in code_extensions:
                    summary["has_code"] = True
                    summary["languages"].add(code_extensions[ext])
    except PermissionError:
        logger.warning(f"Permission denied: {project_path}")
    
    summary["languages"] = list(summary["languages"])
    return summary


def crawl_mcmaker_projects(root_path: str = "/mnt/c/McMaker Projects") -> List[Dict]:
    """
    Crawl the McMaker Projects directory and extract knowledge.
    Returns a list of knowledge entries ready for Medusa's database.
    """
    root = Path(root_path)
    if not root.exists():
        logger.error(f"Root path does not exist: {root_path}")
        return []
    
    knowledge_entries = []
    project_categories = []
    
    logger.info(f"Starting crawl of {root_path}")
    
    # First, catalog top-level categories
    for category_dir in root.iterdir():
        if not category_dir.is_dir() or should_skip_dir(category_dir.name):
            continue
        
        category_name = category_dir.name
        project_categories.append(category_name)
        
        # Add category-level knowledge
        category_entries = []
        category_projects = []
        
        for project_dir in category_dir.iterdir():
            if not project_dir.is_dir() or should_skip_dir(project_dir.name):
                continue
            
            project_name = project_dir.name
            category_projects.append(project_name)
            
            # Extract project details
            summary = extract_project_summary(project_dir)
            
            # Build knowledge entry for this project
            lang_str = ", ".join(summary["languages"]) if summary["languages"] else "Unknown"
            has_code = "Yes" if summary["has_code"] else "No"
            subproj_str = ", ".join(summary["subprojects"][:10]) if summary["subprojects"] else "None"
            
            project_content = f"""Project Name: {project_name}
Category: {category_name}
Path: {summary['path']}
Has Code: {has_code}
Languages: {lang_str}
Subprojects: {subproj_str}
Knowledge Files: {', '.join(summary['files_found'])}
"""
            
            knowledge_entries.append({
                "title": f"McMaker Project: {project_name}",
                "content": project_content,
                "source": f"project_crawler:{category_name}/{project_name}",
                "type": "project",
            })
            
            # Add detailed knowledge from files
            for entry in summary["knowledge_entries"]:
                knowledge_entries.append({
                    "title": f"{project_name} - {entry['file']}",
                    "content": entry["content"],
                    "source": f"project_crawler:{category_name}/{project_name}/{entry['file']}",
                    "type": "documentation",
                })
        
        # Category summary
        category_content = f"""Category: {category_name}
Location: {category_dir}
Projects: {', '.join(category_projects)}
Total Projects: {len(category_projects)}
"""
        knowledge_entries.append({
            "title": f"McMaker Category: {category_name}",
            "content": category_content,
            "source": f"project_crawler:{category_name}",
            "type": "category",
        })
    
    # Master ecosystem entry
    ecosystem_content = f"""McMaker Projects Ecosystem
Root: {root_path}
Total Categories: {len(project_categories)}
Categories: {', '.join(project_categories)}
Total Knowledge Entries: {len(knowledge_entries)}
Crawled At: {datetime.now().isoformat()}
"""
    knowledge_entries.insert(0, {
        "title": "McMaker Projects Master Index",
        "content": ecosystem_content,
        "source": "project_crawler:master",
        "type": "ecosystem",
    })
    
    logger.info(f"Crawl complete. {len(knowledge_entries)} knowledge entries extracted.")
    return knowledge_entries


def save_knowledge_json(entries: List[Dict], output_path: str):
    """Save knowledge entries to a JSON file for inspection/training."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(entries)} entries to {output_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    entries = crawl_mcmaker_projects()
    save_knowledge_json(entries, "/mnt/c/McMaker Projects/Projects/Medusa/medusa/data/mcmaker_knowledge.json")

"""
Final project implementation.
"""

from lab_6_pipeline.pipeline import UDPipeAnalyzer
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
current_working_dir = Path.cwd().resolve()
for import_root in (project_root, current_working_dir):
    import_root_str = str(import_root)
    if import_root_str not in sys.path:
        sys.path.insert(0, import_root_str)

OUTPUT_FILENAME = "auto_annotated.conllu"


def _collect_text_files(corpus_path: Path) -> list[Path]:
    """
    Collect text files from the corpus directory.

    Args:
        corpus_path (Path): Path to a directory with corpus text files.

    Returns:
        list[Path]: Sorted list of discovered .txt files.

    Raises:
        FileNotFoundError: If corpus directory does not exist.
        NotADirectoryError: If corpus path is not a directory.
        ValueError: If corpus directory contains no .txt files.
    """
    if not corpus_path.exists():
        raise FileNotFoundError(f"Corpus folder does not exist: {corpus_path}")
    if not corpus_path.is_dir():
        raise NotADirectoryError(f"Corpus path is not a directory: {corpus_path}")

    text_files = sorted(
        path for path in corpus_path.rglob("*.txt") if path.is_file()
    )
    if not text_files:
        raise ValueError(f"No .txt files found in corpus folder: {corpus_path}")

    return text_files


def _read_corpus(text_files: list[Path]) -> str:
    """
    Join corpus files into one text.

    Args:
        text_files (list[Path]): Text files to read.

    Returns:
        str: Combined corpus text.

    Raises:
        ValueError: If all discovered files are empty.
    """
    texts = [path.read_text(encoding="utf-8").strip() for path in text_files]
    corpus_text = "\n\n".join(text for text in texts if text)
    if not corpus_text:
        raise ValueError("Corpus .txt files are empty")

    return corpus_text


def _analyze_corpus(corpus_text: str) -> str:
    """
    Process corpus text with UDPipeAnalyzer.

    Args:
        corpus_text (str): Combined corpus text.

    Returns:
        str: CoNLL-U annotation.

    Raises:
        ValueError: If analyzer returns no non-empty annotation.
    """
    analyzer = UDPipeAnalyzer()
    analyzed_texts = analyzer.analyze([corpus_text])
    result = "\n\n".join(text.strip() for text in analyzed_texts if text.strip())

    if not result:
        raise ValueError("UDPipeAnalyzer returned an empty result")

    return result.rstrip("\n") + "\n"


def main(corpus_path: Path, dist_path: Path) -> None:
    """
    Generate CoNLL-U file for provided corpus of texts.

    Args:
        corpus_path (Path): Path to folder containing text files.
        dist_path (Path): Path to folder for saving auto_annotated.conllu.
    """
    text_files = _collect_text_files(corpus_path)
    corpus_text = _read_corpus(text_files)
    conllu_text = _analyze_corpus(corpus_text)

    dist_path.mkdir(parents=True, exist_ok=True)
    output_path = dist_path / OUTPUT_FILENAME
    output_path.write_text(conllu_text, encoding="utf-8")


if __name__ == "__main__":
    main(Path(__file__).parent / "assets" / "articles", Path(__file__).parent / "dist")

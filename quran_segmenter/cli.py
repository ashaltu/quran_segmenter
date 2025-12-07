# quran_segmenter/cli.py
"""
Command-line interface for Quran Segmenter.
"""
import argparse
import json
import sys
import logging
from pathlib import Path
from typing import Optional

from .config import Config, get_config
from .pipeline.orchestrator import QuranSegmenterPipeline
from .exceptions import QuranSegmenterError


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def cmd_init(args):
    """Initialize configuration and data directories."""
    config = Config(
        base_dir=Path(args.base_dir),
        data_dir=Path(args.data_dir)
    )
    config.save()
    print(f"Initialized configuration at {config.data_dir / 'config.json'}")
    print(f"Data directory: {config.data_dir}")


def cmd_register(args):
    """Register a new translation."""
    pipeline = QuranSegmenterPipeline()
    pipeline.register_translation(
        translation_id=args.id,
        name=args.name,
        language_code=args.language,
        source_file=Path(args.file),
        spans_embeddings_filepath=Path(args.spans_embeddings_filepath) if args.spans_embeddings_filepath else None,
        segment_embeddings_filepath=Path(args.segment_embeddings_filepath) if args.segment_embeddings_filepath else None
    )
    print(f"Registered translation: {args.id}")


def cmd_list(args):
    """List registered translations."""
    pipeline = QuranSegmenterPipeline()
    translations = pipeline.list_translations()
    
    if not translations:
        print("No translations registered.")
        return
    
    print("\nRegistered Translations:")
    print("-" * 80)
    for t in translations:
        status = "✓ Ready" if t["ready_for_processing"] else "✗ Not ready"
        missing = f" (missing: {', '.join(t['missing'])})" if t["missing"] else ""
        print(f"  {t['id']:<30} {t['language']:<10} {status}{missing}")
    print()


def cmd_prepare(args):
    """Prepare a translation for processing."""
    pipeline = QuranSegmenterPipeline()
    
    try:
        status = pipeline.prepare_translation(
            translation_id=args.translation,
            api_key=args.api_key,
            skip_segmentation=args.skip_segmentation,
            skip_embeddings=args.skip_embeddings,
            force=args.force
        )
        
        print("\nPreparation Status:")
        for step, result in status["steps"].items():
            print(f"  {step}: {result}")
        
        if status.get("ready"):
            print(f"\n✓ Translation '{args.translation}' is ready for processing")
        
    finally:
        pipeline.cleanup()


def cmd_process(args):
    """Process audio to generate segments."""
    pipeline = QuranSegmenterPipeline()
    
    try:
        result = pipeline.process(
            audio_path=Path(args.audio),
            verses=args.verses,
            translation_id=args.translation,
            output_path=Path(args.output) if args.output else None,
            use_cache=not args.no_cache,
            start_server=args.start_server
        )
        
        print(f"\n✓ Processed {len(result.verses)} verses")
        print(f"  Total segments: {sum(len(vs.segments) for vs in result.verses.values())}")
        
        if result.warnings:
            print(f"\nWarnings ({len(result.warnings)}):")
            for w in result.warnings[:5]:
                print(f"  - {w}")
            if len(result.warnings) > 5:
                print(f"  ... and {len(result.warnings) - 5} more")
        
        if args.output:
            print(f"\nOutput saved to: {args.output}")
        else:
            # Print to stdout
            print("\nOutput:")
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
            
    finally:
        pipeline.cleanup()


def cmd_status(args):
    """Show status of a translation."""
    pipeline = QuranSegmenterPipeline()
    
    if args.translation:
        status = pipeline.jumlize.get_segmentation_status(args.translation)
        ready, missing = pipeline.rabtize.is_ready(args.translation)
        
        print(f"\nTranslation: {args.translation}")
        print(f"  Segmented: {status['is_segmented']}")
        if status.get('total_verses'):
            print(f"  Progress: {status['segmented_verses']}/{status['total_verses']} "
                  f"({status['completion_pct']}%)")
        print(f"  Ready for processing: {ready}")
        if missing:
            print(f"  Missing: {', '.join(missing)}")
    else:
        # Show global status
        config = get_config()
        print(f"\nGlobal Status:")
        print(f"  Data directory: {config.data_dir}")
        print(f"  Spans embeddings: {'✓' if config.spans_embeddings_generated else '✗'}")
        print(f"  Registered translations: {len(config.translations)}")


def cmd_clear_cache(args):
    """Clear cached data."""
    from .utils.cache import CacheManager
    config = get_config()
    cache = CacheManager(config.cache_dir)
    cache.clear(args.category)
    print(f"Cache cleared: {args.category or 'all'}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="quran-segmenter",
        description="Generate timed subtitle segments for Quran recitations"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # init
    p_init = subparsers.add_parser("init", help="Initialize configuration")
    p_init.add_argument("--base-dir", default=".", help="Base directory")
    p_init.add_argument("--data-dir", default="./data", help="Data directory")
    p_init.set_defaults(func=cmd_init)
    
    # register
    p_register = subparsers.add_parser("register", help="Register a translation")
    p_register.add_argument("id", help="Translation ID (e.g., en-sahih)")
    p_register.add_argument("file", help="Path to translation JSON file")
    p_register.add_argument("--name", required=True, help="Display name")
    p_register.add_argument("--language", required=True, help="Language code (e.g., en)")
    p_register.add_argument("--spans-embeddings-filepath", required=False, help="Path to spans embeddings file")
    p_register.add_argument("--segment-embeddings-filepath", required=False, help="Path to segment embeddings file")
    p_register.set_defaults(func=cmd_register)
    
    # list
    p_list = subparsers.add_parser("list", help="List translations")
    p_list.set_defaults(func=cmd_list)
    
    # prepare
    p_prepare = subparsers.add_parser("prepare", help="Prepare translation for processing")
    p_prepare.add_argument("translation", help="Translation ID")
    p_prepare.add_argument("--api-key", help="Gemini API key for segmentation")
    p_prepare.add_argument("--skip-segmentation", action="store_true",
                          help="Skip jumlize (for pre-segmented translations)")
    p_prepare.add_argument("--skip-embeddings", action="store_true", help="Skip all embedding generation steps")
    p_prepare.add_argument("--force", action="store_true", help="Force re-run all steps")
    p_prepare.set_defaults(func=cmd_prepare)
    
    # process
    p_process = subparsers.add_parser("process", help="Process audio")
    p_process.add_argument("audio", help="Path to audio file")
    p_process.add_argument("verses", help="Verse spec (e.g., 2:282, 2:1-10, 2)")
    p_process.add_argument("translation", help="Translation ID")
    p_process.add_argument("-o", "--output", help="Output file path")
    p_process.add_argument("--no-cache", action="store_true", help="Disable caching")
    p_process.add_argument("--start-server", action="store_true", help="Start lafzize server if not running")
    p_process.set_defaults(func=cmd_process)
    
    # status
    p_status = subparsers.add_parser("status", help="Show status")
    p_status.add_argument("translation", nargs="?", help="Translation ID (optional)")
    p_status.set_defaults(func=cmd_status)
    
    # clear-cache
    p_cache = subparsers.add_parser("clear-cache", help="Clear cache")
    p_cache.add_argument("--category", choices=["timestamps", "alignments"],
                        help="Category to clear (default: all)")
    p_cache.set_defaults(func=cmd_clear_cache)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    setup_logging(args.verbose)
    
    try:
        args.func(args)
    except QuranSegmenterError as e:
        logging.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(130)


if __name__ == "__main__":
    main()
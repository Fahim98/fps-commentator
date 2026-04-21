"""
FPS Commentator CLI
"""

import asyncio
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich import print as rprint

from src.pipeline.commentator import FPSCommentator, CommentaryConfig

console = Console()


@click.command()
@click.argument("video_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--persona", "-p",
    type=click.Choice(["hype_caster", "analyst", "funny", "chill"]),
    default="hype_caster",
    show_default=True,
    help="Commentary style/personality",
)
@click.option(
    "--density", "-d",
    type=click.FloatRange(0.0, 1.0),
    default=0.6,
    show_default=True,
    help="Commentary density: 0.0 = sparse, 1.0 = constant",
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path (default: <input>_commentary.<ext>)",
)
@click.option(
    "--no-duck",
    is_flag=True,
    default=False,
    help="Don't duck game audio during commentary",
)
@click.option(
    "--duck-volume",
    type=click.FloatRange(0.0, 1.0),
    default=0.3,
    show_default=True,
    help="Game audio volume while commentary plays (0.0-1.0)",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def main(video_path, persona, density, output, no_duck, duck_volume, verbose):
    """
    🎮 FPS Commentator — Add AI voiceover to your game clips.

    \b
    Examples:
      fps-commentator clip.mp4
      fps-commentator clip.mp4 --persona analyst --density 0.4
      fps-commentator clip.mp4 --persona funny -o funny_version.mp4
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)

    console.print(Panel.fit(
        f"[bold cyan]FPS Commentator[/bold cyan]\n"
        f"[dim]Input:[/dim] {video_path.name}\n"
        f"[dim]Persona:[/dim] {persona.replace('_', ' ').title()}\n"
        f"[dim]Density:[/dim] {density:.0%}",
        border_style="cyan",
    ))

    config = CommentaryConfig(
        persona=persona,
        commentary_density=density,
        duck_game_audio=not no_duck,
        duck_volume=duck_volume,
    )

    result = asyncio.run(_run(video_path, output, config))

    if result.success:
        console.print(f"\n[bold green]✓ Done![/bold green]")
        console.print(f"  Events detected:  [cyan]{result.events_detected}[/cyan]")
        console.print(f"  Commentary lines: [cyan]{result.commentary_lines}[/cyan]")
        console.print(f"  Output:           [cyan]{result.output_path}[/cyan]\n")
    else:
        console.print(f"\n[bold red]✗ Failed:[/bold red] {result.error}\n")
        sys.exit(1)


async def _run(video_path, output_path, config):
    commentator = FPSCommentator(config=config)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing...", total=None)

        # Patch logger to update progress description
        original_info = logging.getLogger("fps_commentator").info

        def progress_log(msg, *args, **kwargs):
            progress.update(task, description=msg)
            original_info(msg, *args, **kwargs)

        logging.getLogger("src.pipeline.commentator").info = progress_log

        return await commentator.process(video_path, output_path)


if __name__ == "__main__":
    main()

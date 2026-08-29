import asyncio
import logging
import os
import sys
import warnings

# Ensure workspace root is in sys.path for direct execution
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Suppress ResourceWarning on Windows subprocess pipes and deprecated package warnings
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

from src.pipeline import run_pipeline_async

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


BANNER = r"""
 ╔═══════════════════════════════════════════════════════════════════════╗
 ║    ____            _   ______     __        __           ____         ║
 ║   / __ \___  ____ _/ | / / ___/____/ /_____ _/ /____     / __/  _   _ ║
 ║  / /_/ / _ \/ __ `/  |/ /\__ \/ ___/ __/ __ `/ __/ _ \   / /_  | | / /║
 ║ / _, _/  __/ /_/ / /|  /___/ / /__/ /_/ /_/ / /_/  __/  / __/  | |/ / ║
 ║/_/ |_|\___/\__,_/_/ |_//____/\___/\__/\__,_/\__/\___/  /_/     |___/  ║
 ║                                                                       ║
 ║           🏠 Real Estate Local Scraper & LLM Extractor 🤖             ║
 ╚═══════════════════════════════════════════════════════════════════════╝
"""


def prompt_choice(prompt_text: str, options: list[str], default_idx: int = 0) -> str:
    """Prompts the user to select an option from a numbered list."""
    print(f"\n{prompt_text}")
    for idx, opt in enumerate(options, start=1):
        marker = "(Padrão)" if idx - 1 == default_idx else ""
        print(f"  [{idx}] {opt} {marker}")

    while True:
        raw = input(f"Selecione [1-{len(options)}] ou ENTER para padrão: ").strip()
        if not raw:
            return options[default_idx]
        if raw.isdigit():
            val = int(raw)
            if 1 <= val <= len(options):
                return options[val - 1]
        print("Opção inválida, tente novamente.")


def prompt_text(prompt_label: str, default_value: str) -> str:
    """Prompts the user for a text value with a default fallback."""
    raw = input(f"{prompt_label} [{default_value}]: ").strip()
    return raw if raw else default_value


def print_ascii_table(df, max_rows: int = 10):
    """Renders a clean ASCII table preview of the extracted properties dataframe."""
    if df.empty:
        print("\n┌────────────────────────────────────────┐")
        print("│        Nenhum imóvel extraído.         │")
        print("└────────────────────────────────────────┘")
        return

    columns_to_show = ["title", "price", "property_type", "neighborhood", "bedrooms", "area_m2"]
    available_cols = [c for c in columns_to_show if c in df.columns]

    preview_df = df[available_cols].head(max_rows).copy()

    # Truncate long titles for ASCII table formatting
    if "title" in preview_df.columns:
        preview_df["title"] = preview_df["title"].apply(lambda t: (str(t)[:32] + "..") if len(str(t)) > 34 else str(t))

    print("\n" + "=" * 80)
    print(f"📊 PRÉVIA DOS IMÓVEIS EXTRAÍDOS (Exibindo até {max_rows} de {len(df)} registros):")
    print("=" * 80)
    print(preview_df.to_string(index=False))
    print("=" * 80)


async def main():
    print(BANNER)
    print("┌──────────────────────── CONFIGURAÇÃO DA BUSCA ────────────────────────┐")
    print("│ Configure os filtros desejados para o rastreamento e extração com IA. │")
    print("└───────────────────────────────────────────────────────────────────────┘\n")

    # 1. Inputs interativos
    country = prompt_text("1. País", "Brasil")
    city = prompt_text("2. Cidade", "Jardim Botânico DF")

    prop_types = ["Todos", "Apartamento", "Casa", "Terreno", "Comercial", "Cobertura", "Studio", "Chácara"]
    selected_prop_type = prompt_choice("3. Tipo de Imóvel:", prop_types, default_idx=2)

    trans_types = ["Venda", "Aluguel", "Todos"]
    selected_trans_type = prompt_choice("4. Tipo de Negócio:", trans_types, default_idx=0)

    max_curated_str = prompt_text("5. Quantos sites principais a IA deve escolher e analisar?", "2")
    try:
        max_curated = int(max_curated_str)
    except ValueError:
        max_curated = 2

    max_pages_str = prompt_text("6. Quantidade de páginas (abas) por site", "1")
    try:
        max_pages = int(max_pages_str)
    except ValueError:
        max_pages = 1

    # Resumo visual
    print("\n" + "┌" + "─" * 70 + "┐")
    print("│" + " " * 24 + "RESUMO DA EXECUÇÃO" + " " * 28 + "│")
    print("├" + "─" * 70 + "┤")
    print(f"│  País:              {country:<49}│")
    print(f"│  Cidade:            {city:<49}│")
    print(f"│  Tipo de Imóvel:    {selected_prop_type:<49}│")
    print(f"│  Transação:         {selected_trans_type:<49}│")
    print(f"│  Sites pela IA:     Top {max_curated} sites mais famosos e relevantes{'':<18}│")
    print(f"│  Páginas por Site:  {max_pages} página(s){'':<36}│")
    print("└" + "─" * 70 + "┘\n")

    confirm = input("Pressione ENTER para iniciar o scraping ou 'q' para cancelar: ").strip().lower()
    if confirm == "q":
        print("Operação cancelada pelo usuário.")
        return

    print("\n🚀 Iniciando pipeline com Curadoria por IA...\n")

    try:
        result = await run_pipeline_async(
            country=country,
            city=city,
            property_type=selected_prop_type,
            transaction_type=selected_trans_type,
            max_sites_to_curate=max_curated,
            max_pages_per_site=max_pages,
            save_to_csv=True
        )

        print("\n" + "╔" + "═" * 70 + "╗")
        print(f"║  RESULTADO FINAL: {len(result.properties)} imóveis extraídos com sucesso!{'':<21}║")
        print("╚" + "═" * 70 + "╝")

        if result.curated_sites:
            print("\n🌐 Sites selecionados pela IA:")
            for idx, site in enumerate(result.curated_sites, start=1):
                print(f"  [{idx}] {site}")

        # Exibe a tabela ASCII formatada
        print_ascii_table(result.dataframe, max_rows=10)

        if result.saved_file_path:
            print(f"\n💾 Arquivo CSV consolidado salvo em:\n  👉 {result.saved_file_path}\n")

    except Exception as error:
        print(f"\n❌ Erro durante o pipeline: {error}")


if __name__ == "__main__":
    asyncio.run(main())

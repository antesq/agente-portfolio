"""Modelos de dados do portfólio de projetos MELI/Install.

O esquema espelha a planilha "MELI Portfólio de Projetos de Transportes da
Install". Cada `ProjetoMeli` é uma obra/contratação; os campos de data são os
milestones principais; `status_geral` + `motivo_bloqueio` capturam o risco.

Estas estruturas são o "contrato" entre o Claude e o resto do sistema:
o agente devolve JSON neste formato, nós validamos e persistimos/exportamos.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any

# Valores canônicos de Status Geral (usados para cores e para o resumo).
STATUS_VALIDOS = [
    "Dentro do prazo",
    "Em risco",
    "EM ATRASO",
    "Congelado",
    "Cancelado",
    "Concluído",
]


@dataclass
class Acao:
    """Um item da lista de ações (o que fazer a seguir)."""
    acao: str
    projeto: str = ""              # código do projeto relacionado (ex.: "1591")
    origem: str = ""              # de onde veio: E-mail, WhatsApp, Smartsheet, Manual
    responsavel: str = ""
    prazo: str = ""              # ISO AAAA-MM-DD ou texto (ex.: "21/out./26")
    prioridade: str = "Média"    # Baixa | Média | Alta | Urgente
    status: str = "Pendente"     # Pendente | Em andamento | Concluída


@dataclass
class ProjetoMeli:
    """Uma linha da aba 'Contratação Meli' — uma obra do portfólio.

    Os nomes dos campos são snake_case; o mapeamento para os títulos exatos das
    colunas da planilha fica em COLUNAS_PLANILHA (abaixo), usado na exportação.
    """
    projeto: str                             # "Projeto" (código, ex.: "1591")
    unidade_meli: str = ""                  # "Unidade (Cód. Meli)" (ex.: "SSP15")
    pm_meli: str = ""                       # "PM MELI"
    aplicacoes_install: str = ""            # "Aplicações Install"
    cidade: str = ""
    escopo_atual: str = ""                  # "Escopo atual" (escopo técnico)
    layout_em_proposta: str = ""
    proposta_tecnica_contratada: str = ""   # ex.: "PPT-BR-2026-07-1704" (agente atualiza)
    prazo_fr_contratado: str = ""
    recebimento_layout_meli: str = ""
    data_limite_recebimento_layout: str = ""
    layout_enviado_aprovacao: str = ""      # "Layout Install enviado para aprovação?"
    data_limite_envio_layout: str = ""
    layout_aprovado: str = ""               # "Layout Aprovado?"
    data_limite_aprovacao_layout: str = ""
    carregamento_install: str = ""
    fr_install: str = ""
    status_geral: str = "Dentro do prazo"
    motivo_bloqueio: str = ""
    responsavel_pendencia: str = ""
    observacoes: str = ""                    # "Observações (histórico)"

    def resumo_curto(self) -> str:
        return f"[{self.projeto}] {self.unidade_meli} — {self.cidade} — {self.status_geral}"


@dataclass
class Portfolio:
    """O portfólio completo: várias obras + o plano de ações consolidado."""
    titulo: str = "MELI — Portfólio de Projetos de Transportes da Install"
    projetos: list[ProjetoMeli] = field(default_factory=list)
    acoes: list[Acao] = field(default_factory=list)

    # -- Busca / atualização por código de projeto --------------------------
    def buscar(self, codigo: str) -> ProjetoMeli | None:
        for p in self.projetos:
            if p.projeto.strip() == str(codigo).strip():
                return p
        return None

    def upsert(self, projeto: ProjetoMeli) -> str:
        """Insere ou atualiza um projeto pelo código. Retorna 'novo'|'atualizado'."""
        existente = self.buscar(projeto.projeto)
        if existente is None:
            self.projetos.append(projeto)
            return "novo"
        # Atualiza só os campos preenchidos (não sobrescreve com vazio).
        for f in fields(ProjetoMeli):
            novo_valor = getattr(projeto, f.name)
            if novo_valor not in ("", None):
                setattr(existente, f.name, novo_valor)
        return "atualizado"


# Ordem e títulos EXATOS das colunas na aba "Contratação Meli" da planilha.
COLUNAS_PLANILHA: list[tuple[str, str]] = [
    ("projeto", "Projeto"),
    ("unidade_meli", "Unidade (Cód. Meli)"),
    ("pm_meli", "PM MELI"),
    ("aplicacoes_install", "Aplicações Install"),
    ("cidade", "Cidade"),
    ("escopo_atual", "Escopo atual"),
    ("layout_em_proposta", "Layout em proposta"),
    ("proposta_tecnica_contratada", "Proposta técnica contratada"),
    ("prazo_fr_contratado", "Prazo de FR Contratado"),
    ("recebimento_layout_meli", "Recebimento do layout Meli"),
    ("data_limite_recebimento_layout", "Data limite para recebimento do layout"),
    ("layout_enviado_aprovacao", "Layout Install enviado para aprovação?"),
    ("data_limite_envio_layout", "Data Limite de envio do Layout"),
    ("layout_aprovado", "Layout Aprovado?"),
    ("data_limite_aprovacao_layout", "Data Limite de Aprovação do Layout"),
    ("carregamento_install", "Carregamento Install"),
    ("fr_install", "FR Install"),
    ("status_geral", "Status Geral"),
    ("motivo_bloqueio", "Motivo do bloqueio"),
    ("responsavel_pendencia", "Responsável pela pendência"),
    ("observacoes", "Observações (histórico)"),
]


# --------------------------------------------------------------------------
# Serialização (persistência em JSON) e conversão a partir do JSON do Claude.
# --------------------------------------------------------------------------
def portfolio_para_dict(pf: Portfolio) -> dict[str, Any]:
    return {
        "titulo": pf.titulo,
        "projetos": [asdict(p) for p in pf.projetos],
        "acoes": [asdict(a) for a in pf.acoes],
    }


def portfolio_de_dict(dados: dict[str, Any]) -> Portfolio:
    """Converte um dict (JSON salvo ou vindo do Claude) em Portfolio.

    Tolerante a campos ausentes: chaves que faltarem usam o padrão do dataclass.
    """
    projetos = [
        ProjetoMeli(**_so_campos(p, ProjetoMeli))
        for p in dados.get("projetos", [])
        if p.get("projeto")  # ignora linhas sem código de projeto
    ]
    acoes = [Acao(**_so_campos(a, Acao)) for a in dados.get("acoes", [])]
    return Portfolio(
        titulo=dados.get("titulo", "MELI — Portfólio de Projetos de Transportes da Install"),
        projetos=projetos,
        acoes=acoes,
    )


def _so_campos(d: dict[str, Any], cls: type) -> dict[str, Any]:
    """Filtra o dict deixando só as chaves que o dataclass conhece."""
    validos = {f.name for f in fields(cls)}
    return {k: v for k, v in d.items() if k in validos}

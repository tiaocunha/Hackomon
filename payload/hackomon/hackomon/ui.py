"""480x222 layout and screens."""

import time

from .constants import (
    COLOR_BG,
    COLOR_CYAN,
    COLOR_GREEN,
    COLOR_MUTED,
    COLOR_PANEL,
    COLOR_PANEL_ALT,
    COLOR_PURPLE,
    COLOR_RED,
    COLOR_TEXT,
    COLOR_YELLOW,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from .evolution import gate_status
from .backgrounds import draw_background
from .sprites import draw_sprite, iter_color_runs, sprite_frame


ACTIONS = ("Alimentar", "Brincar", "Descansar", "Bestiario", "Redes / Laboratorio", "Expedicao", "Ajuda")
NETWORK_MENU = (("visit_scan", "Atendimento: buscar redes do cliente"),
                ("WIFI", "Descobrir Wi-Fi com GPS"), ("BLE", "Descobrir Bluetooth LE com GPS"),
                ("export", "Exportar CSV"), ("upload", "Enviar ao WDGWars"),
                ("capture", "Lab: capturar EAPOL (20s)"),
                ("test", "Lab: testar dicionario (30s)"),
                ("bluetooth_audit", "Lab: auditar Bluetooth"))


def _bar(display, x, y, width, value, color, label):
    value = max(0, min(100, int(value)))
    display.draw_text(x, y, label, COLOR_MUTED, 1)
    display.fill_rect(x + 48, y + 1, width, 7, COLOR_PANEL_ALT)
    display.fill_rect(x + 48, y + 1, max(1, width * value // 100), 7, color)
    display.draw_text(x + 52 + width, y, "%3d" % value, COLOR_TEXT, 1)


def _panel(display, x, y, width, height, color=COLOR_PANEL):
    display.fill_rect(x, y, width, height, color)
    display.fill_rect(x, y, width, 1, COLOR_CYAN)
    display.fill_rect(x, y + height - 1, width, 1, COLOR_CYAN)
    display.fill_rect(x, y, 1, height, COLOR_CYAN)
    display.fill_rect(x + width - 1, y, 1, height, COLOR_CYAN)


def draw_silhouette(display, creature, x, y, scale=4):
    frame = sprite_frame(creature, "idle", 0)
    for run_x, run_y, width, _color in iter_color_runs(frame):
        display.fill_rect(x + run_x * scale, y + run_y * scale, width * scale, scale, COLOR_MUTED)


class HackomonUI:
    def __init__(self, display, catalog):
        self.display = display
        self.catalog = catalog

    def _header(self, title, state):
        display = self.display
        display.fill_rect(0, 0, SCREEN_WIDTH, 20, COLOR_PANEL_ALT)
        display.draw_text(7, 5, title, COLOR_CYAN, 1)
        right = "LV %02d  XP %04d" % (state.level, state.xp)
        display.draw_text(SCREEN_WIDTH - display.text_width(right, 1) - 7, 5, right, COLOR_TEXT, 1)

    def home(self, state, selected, pose, frame_index, message=""):
        display = self.display
        creature = self.catalog.creature(state.creature_id)
        family = self.catalog.family_by_id[creature["family_id"]]
        display.clear(COLOR_BG)
        self._header("HACKOMON", state)
        _panel(display, 8, 27, 174, 164)
        draw_background(display, creature, 9, 28, 172, 140, frame_index)
        draw_sprite(display, creature, 31, 39, scale=4, pose=pose, frame_index=frame_index)
        display.draw_text_centered(171, creature["name"][:24], COLOR_TEXT, 1)
        display.draw_text_centered(181, "%s / %s" % (family["name"], creature["stage_name"]), COLOR_MUTED, 1)

        _panel(display, 190, 27, 282, 164)
        _bar(display, 202, 38, 96, state.hunger, COLOR_YELLOW, "FOME")
        _bar(display, 202, 52, 96, state.happiness, COLOR_PURPLE, "HUMOR")
        _bar(display, 202, 66, 96, state.energy, COLOR_GREEN, "ENERG")
        display.draw_text(202, 83, "CUIDADO %02d  BEM-ESTAR %02d" % (state.care_points, state.wellness), COLOR_MUTED, 1)

        for index, label in enumerate(ACTIONS):
            y = 99 + index * 12
            if index == selected:
                display.fill_rect(199, y - 2, 262, 12, COLOR_PANEL_ALT)
                color = COLOR_CYAN
                prefix = "> "
            else:
                color = COLOR_TEXT
                prefix = "  "
            display.draw_text(204, y, prefix + label, color, 1)

        footer = message or "D-PAD escolhe  A confirma  B sai"
        display.fill_rect(0, 197, SCREEN_WIDTH, SCREEN_HEIGHT - 197, COLOR_PANEL_ALT)
        display.draw_text_centered(205, footer[:72], COLOR_TEXT if not message else COLOR_YELLOW, 1)
        display.flip()

    def bestiary(self, state, index, frame_index=0):
        display = self.display
        creature = self.catalog.creatures[index]
        family = self.catalog.family_by_id[creature["family_id"]]
        evolution_line = self.catalog.line_by_id[creature["line_id"]]
        unlocked = creature["id"] in state.discovered
        display.clear(COLOR_BG)
        self._header("BESTIARIO  %03d/250" % (index + 1), state)
        _panel(display, 8, 28, 174, 164)
        draw_background(display, creature, 9, 29, 172, 139, frame_index)
        if unlocked:
            draw_sprite(display, creature, 31, 39, scale=4, pose="idle", frame_index=frame_index)
        else:
            draw_silhouette(display, creature, 31, 39, scale=4)
        display.draw_text_centered(176, "DESCOBERTO" if unlocked else "BLOQUEADO", COLOR_GREEN if unlocked else COLOR_RED, 1)

        _panel(display, 190, 28, 282, 164)
        display.draw_text(204, 42, creature["name"] if unlocked else "???", COLOR_TEXT, 2)
        display.draw_text(204, 68, "Familia: %s" % family["name"], COLOR_MUTED, 1)
        display.draw_text(204, 82, "Linha: %s" % evolution_line["name"], COLOR_MUTED, 1)
        display.draw_text(204, 96, "Estagio: %s" % creature["stage_name"], COLOR_MUTED, 1)
        display.draw_text(204, 110, "Raridade: %s" % creature["rarity"], COLOR_MUTED, 1)
        display.draw_text(204, 124, "Temperamento: %s" % creature["temperament"], COLOR_MUTED, 1)
        display.draw_text(204, 151, "Descobertos: %d / 250" % len(state.discovered), COLOR_CYAN, 1)
        display.draw_text_centered(205, "ESQ/DIR 1  CIMA/BAIXO 5  A/B volta", COLOR_TEXT, 1)
        display.flip()

    def expedition(self, state, summary, message, frame_index=0, pose="idle"):
        display = self.display
        creature = self.catalog.creature(state.creature_id)
        display.clear(COLOR_BG)
        self._header("EXPEDICAO HACKOMON", state)
        _panel(display, 8, 27, 174, 164)
        draw_background(display, creature, 9, 28, 172, 140, frame_index)
        if summary and summary["status"] == "running" and time.time() - summary.get("gps_at", 0) > 15 and pose == "idle":
            pose = "sad"
        draw_sprite(display, creature, 31, 39, scale=4, pose=pose, frame_index=frame_index)
        display.draw_text_centered(174, creature["name"][:24], COLOR_TEXT, 1)
        _panel(display, 190, 27, 282, 164)
        if summary is None:
            display.draw_text(202, 43, "Vamos explorar?", COLOR_CYAN, 2)
            display.draw_text(202, 78, "A inicia  Wi-Fi + BLE", COLOR_TEXT, 1)
            display.draw_text(202, 98, "GPS externo via gpsd", COLOR_MUTED, 1)
            display.draw_text(202, 122, "Offline; sincronize depois", COLOR_MUTED, 1)
        else:
            labels = {"running": "EXPLORANDO", "paused": "PAUSADA", "ending": "ENCERRANDO", "ended": "FINALIZADA"}
            display.draw_text(202, 39, labels.get(summary["status"], "PAUSADA"), COLOR_CYAN, 1)
            display.draw_text(202, 59, "Wi-Fi %d  BLE %d" % (summary["wifi"], summary["ble"]), COLOR_TEXT, 1)
            display.draw_text(202, 77, "GPS %d  Sem GPS %d" % (summary["located"], summary["unlocated"]), COLOR_TEXT, 1)
            display.draw_text(202, 95, "Percurso aprox. %.2f km" % (summary["distance_m"] / 1000), COLOR_TEXT, 1)
            display.draw_text(202, 113, "XP da expedicao: %d" % summary["xp"], COLOR_GREEN, 1)
            display.draw_text(202, 131, "Testes %d  Recuperacoes %d" % (summary["audits"], summary["recoveries"]), COLOR_MUTED, 1)
            gps = "GPS recente" if time.time() - summary.get("gps_at", 0) <= 15 else "GPS ausente/antigo"
            display.draw_text(202, 154, gps, COLOR_YELLOW, 1)
            display.draw_text(202, 173, "A inicia/pausa  ESQ encerra", COLOR_TEXT, 1)
        display.draw_text_centered(198, message[:72], COLOR_YELLOW, 1)
        display.draw_text_centered(212, "DIR: escolher alvo autorizado  B: voltar", COLOR_TEXT, 1)
        display.flip()

    def help(self, state):
        display = self.display
        display.clear(COLOR_BG)
        self._header("AJUDA E EVOLUCAO", state)
        _panel(display, 8, 28, 464, 164)
        display.draw_text(20, 41, "Alimentar: recupera fome", COLOR_TEXT, 1)
        display.draw_text(20, 57, "Brincar: aumenta humor e XP", COLOR_TEXT, 1)
        display.draw_text(20, 73, "Descansar: recupera energia", COLOR_TEXT, 1)
        status = gate_status(state)
        if status is None:
            display.draw_text(20, 101, "Forma final alcancada!", COLOR_GREEN, 2)
        else:
            display.draw_text(20, 96, "PROXIMA EVOLUCAO", COLOR_CYAN, 1)
            display.draw_text(20, 113, "Nivel     %d / %d" % status["level"], COLOR_TEXT, 1)
            display.draw_text(20, 129, "Cuidados  %d / %d" % status["care"], COLOR_TEXT, 1)
            display.draw_text(20, 145, "Bem-estar %d / %d" % status["wellness"], COLOR_TEXT, 1)
        display.draw_text(20, 171, "Atendimento: descubra e escolha a rede do cliente.", COLOR_MUTED, 1)
        display.draw_text_centered(205, "A ou B volta", COLOR_TEXT, 1)
        display.flip()

    def network(self, state, selected, message, busy=False, confirm=False):
        display = self.display
        display.clear(COLOR_BG)
        self._header("REDES / LABORATORIO", state)
        _panel(display, 8, 28, 464, 164)
        display.draw_text(20, 38, "Fila: %d/500  XP exploracao: %d" % (
            len(state.network_queue), state.exploration_xp), COLOR_CYAN, 1)
        if confirm:
            display.draw_text(20, 66, "Enviar registros ao WDGWars?", COLOR_YELLOW, 2)
            display.draw_text(20, 96, "Inclui nomes, enderecos, sinal e GPS.", COLOR_TEXT, 1)
            display.draw_text(20, 116, "Capturas e senhas permanecem locais.", COLOR_TEXT, 1)
            display.draw_text(20, 150, "A envia por HTTPS  B cancela", COLOR_CYAN, 1)
        else:
            for index, (_action, label) in enumerate(NETWORK_MENU):
                y = 55 + index * 16
                if selected == index:
                    display.fill_rect(17, y - 3, 446, 15, COLOR_PANEL_ALT)
                display.draw_text(22, y, ("> " if selected == index else "  ") + label,
                                  COLOR_CYAN if selected == index else COLOR_TEXT, 1)
        display.draw_text_centered(198, message[:72], COLOR_YELLOW, 1)
        display.draw_text_centered(212, "Aguarde a operacao" if busy else "A confirma  B volta", COLOR_TEXT, 1)
        display.flip()

    def visit(self, state, networks, selected, message, busy=False, report=None):
        display = self.display
        display.clear(COLOR_BG)
        self._header("ATENDIMENTO AO CLIENTE", state)
        _panel(display, 8, 28, 464, 164)
        if report is not None:
            target = report["target"]
            display.draw_text(20, 39, str(target.get("name") or "Rede oculta")[:42], COLOR_CYAN, 1)
            display.draw_text(20, 56, "%s  %s" % (target["mac"], target["auth"]), COLOR_TEXT, 1)
            display.draw_text(20, 77, "Observacoes: %d (nao sao exploracoes confirmadas)" % len(report["findings"]), COLOR_YELLOW, 1)
            display.draw_text(20, 97, "Captura: " + report["capture"]["status"], COLOR_TEXT, 1)
            display.draw_text(20, 114, "Dicionario: " + report["dictionary"]["status"], COLOR_TEXT, 1)
            display.draw_text(20, 139, "Relatorio local: hackomon/visits/*.json", COLOR_MUTED, 1)
            display.draw_text(20, 158, "Nao enviado ao WDGWars", COLOR_MUTED, 1)
        else:
            display.draw_text(20, 38, "Escolha o AP autorizado pelo cliente; A avalia", COLOR_YELLOW, 1)
            start = selected // 5 * 5
            for row, index in enumerate(range(start, min(start + 5, len(networks)))):
                target = networks[index]
                y = 61 + row * 24
                if index == selected:
                    display.fill_rect(17, y - 3, 446, 23, COLOR_PANEL_ALT)
                label = str(target.get("name") or "Rede oculta")[:29]
                display.draw_text(22, y, "%s %s %ddBm" % (">" if index == selected else " ", label, target["rssi"]), COLOR_CYAN if index == selected else COLOR_TEXT, 1)
                display.draw_text(34, y + 10, "%s  %s" % (target["mac"], target["auth"]), COLOR_MUTED, 1)
            display.draw_text(20, 181, "GPS dispensado; vizinhos nao entram no atendimento", COLOR_MUTED, 1)
        display.draw_text_centered(198, message[:72], COLOR_YELLOW, 1)
        display.draw_text_centered(212, "Aguarde a operacao" if busy else "CIMA/BAIXO escolhe  ESQ atualiza  B volta", COLOR_TEXT, 1)
        display.flip()


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
from .expedition import sensor_status
from .sync import guidance
from .missions import cards as mission_cards
from .progression import level_progress
from . import generations as lifecycle
from .backgrounds import draw_background
from .sprites import draw_sprite, iter_color_runs, sprite_frame


ACTIONS = ("Alimentar", "Brincar", "Descansar", "Bestiario", "Redes / Laboratorio", "Expedicao", "Ajuda", "Geracoes / Ovos")
NETWORK_MENU = (("visit_scan", "Atendimento: buscar redes do cliente"),
                ("WIFI", "Descobrir Wi-Fi com GPS"), ("BLE", "Descobrir Bluetooth LE com GPS"),
                ("export", "Exportar CSV"), ("upload", "WDGWars: sincronizacao e conta"),
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
        right = "TR %02d XP %d | PET %02d" % (state.trainer_level, state.trainer_xp, state.level)
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
        name = creature["name"][:24]
        display.draw_text(8 + max(0, (174 - display.text_width(name)) // 2), 170, name, COLOR_TEXT, 1)
        display.draw_text(14, 182, lifecycle.age_label(state)[:27], COLOR_MUTED, 1)

        _panel(display, 190, 27, 282, 164)
        _bar(display, 202, 38, 96, state.hunger, COLOR_YELLOW, "FOME")
        _bar(display, 202, 52, 96, state.happiness, COLOR_PURPLE, "HUMOR")
        _bar(display, 202, 66, 96, state.energy, COLOR_GREEN, "ENERG")
        display.draw_text(202, 83, "CUID %d + VINC %d | BEM %d" % (
            state.care_points, state.field_bond, state.wellness), COLOR_MUTED, 1)

        for index, label in enumerate(ACTIONS):
            y = 99 + index * 11
            if index == selected:
                display.fill_rect(199, y - 2, 262, 12, COLOR_PANEL_ALT)
                color = COLOR_CYAN
                prefix = "> "
            else:
                color = COLOR_TEXT
                prefix = "  "
            display.draw_text(204, y, prefix + label, color, 1)

        footer = message or ("Ciclo encerrado: abra Geracoes / Ovos" if state.life_status != "alive" else
                             "Evolucao pronta: Geracoes / Ovos" if state.branch_pending else "D-PAD escolhe  A confirma  B sai")
        display.fill_rect(0, 193, SCREEN_WIDTH, SCREEN_HEIGHT - 193, COLOR_PANEL_ALT)
        current, needed = level_progress(state)
        progress = "Pet: proximo nivel %d/%d XP" % (current, needed) if needed else "Pet no nivel maximo; carreira continua"
        display.draw_text_centered(195, progress, COLOR_CYAN, 1)
        display.draw_text_centered(209, footer[:72], COLOR_TEXT if not message else COLOR_YELLOW, 1)
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

    def expedition(self, state, summary, message, frame_index=0, pose="idle", details=False, now=None,
                   mission_page=False, companion=""):
        now = time.time() if now is None else now
        display = self.display
        creature = self.catalog.creature(state.creature_id)
        display.clear(COLOR_BG)
        self._header("EXPEDICAO HACKOMON", state)
        _panel(display, 8, 27, 174, 164)
        draw_background(display, creature, 9, 28, 172, 140, frame_index)
        if summary and summary["status"] == "running" and sensor_status(summary, "gps", now)[0] != "ok" and pose == "idle":
            pose = "sad"
        draw_sprite(display, creature, 31, 39, scale=4, pose=pose, frame_index=frame_index)
        name = creature["name"][:24]
        display.draw_text(8 + max(0, (174 - display.text_width(name)) // 2), 170, name, COLOR_TEXT, 1)
        if companion:
            display.draw_text(14, 182, companion[:27], COLOR_YELLOW, 1)
        _panel(display, 190, 27, 282, 164)
        if summary is None:
            display.draw_text(202, 43, "Vamos explorar?", COLOR_CYAN, 2)
            display.draw_text(202, 78, "A inicia  Wi-Fi + BLE", COLOR_TEXT, 1)
            display.draw_text(202, 98, "GPS externo do Pager", COLOR_MUTED, 1)
            display.draw_text(202, 122, "Offline; sincronize depois", COLOR_MUTED, 1)
        elif mission_page:
            display.draw_text(202, 39, "MISSOES DE EXPLORACAO", COLOR_CYAN, 1)
            for index, card in enumerate(mission_cards(state, summary)):
                y = 61 + index * 36
                display.draw_text(202, y, card["title"], COLOR_GREEN if card["earned"] else COLOR_TEXT, 1)
                text = "MEDALHA CONQUISTADA" if card["earned"] else "%d/%d | %s" % (card["value"], card["target"], card["detail"])
                display.draw_text(202, y + 13, text[:43], COLOR_MUTED, 1)
            display.draw_text(202, 172, "Medalhas salvas; revisitas apos 6h", COLOR_YELLOW, 1)
        elif details:
            seconds = summary.get("active_seconds", 0)
            if summary["status"] == "running":
                seconds += max(0, int(now) - summary.get("active_since", int(now)))
            display.draw_text(202, 39, "RESUMO | %d min ativos" % (seconds // 60), COLOR_CYAN, 1)
            display.draw_text(202, 59, "Wi-Fi %d  BLE %d" % (summary["wifi"], summary["ble"]), COLOR_TEXT, 1)
            display.draw_text(202, 77, "%.2f km  XP +%d" % (summary["distance_m"] / 1000, summary["xp"]), COLOR_GREEN, 1)
            display.draw_text(202, 95, "Novos %d | Revisitas %d" % (summary.get("rewarded_discoveries", 0), summary.get("revisit_awards", 0)), COLOR_TEXT, 1)
            breakdown = summary.get("xp_breakdown", {})
            hint = "XP atividade %d | percurso %d" % (breakdown.get("activity", 0), breakdown.get("distance", 0))
            display.draw_text(202, 108, hint, COLOR_MUTED, 1)
            display.draw_text(202, 123, "Com GPS %d / sem %d" % (summary["located"], summary["unlocated"]), COLOR_TEXT, 1)
            upload = summary.get("upload", {})
            count = upload.get("pending")
            display.draw_text(202, 139, "WDG pendentes: %s" % (count if count is not None else "?"), COLOR_YELLOW, 1)
            note = upload.get("message", "BAIXO para atualizar pendencias")
            display.draw_text(202, 155, note[:43], COLOR_MUTED, 1)
            display.draw_text(202, 164, note[43:86], COLOR_MUTED, 1)
            display.draw_text(202, 179, "A inicia/pausa  ESQ encerra", COLOR_TEXT, 1)
        else:
            labels = {"running": "EXPLORANDO", "paused": "PAUSADA", "ending": "ENCERRANDO", "ended": "FINALIZADA"}
            display.draw_text(202, 39, labels.get(summary["status"], "PAUSADA"), COLOR_CYAN, 1)
            display.draw_text(202, 59, "Wi-Fi %d  BLE %d" % (summary["wifi"], summary["ble"]), COLOR_TEXT, 1)
            display.draw_text(202, 77, "GPS %d  Sem GPS %d" % (summary["located"], summary["unlocated"]), COLOR_TEXT, 1)
            display.draw_text(202, 95, "%.2f km  XP %d" % (summary["distance_m"] / 1000, summary["xp"]), COLOR_GREEN, 1)
            for key, label, y in (("wifi", "WiFi", 111), ("ble", "BLE", 133)):
                status, detail = sensor_status(summary, key, now)
                text = "%s: %s" % (label, detail)
                # Keep each radio's status visible; GPS errors never overwrite it.
                color = {"error": COLOR_RED, "ok": COLOR_GREEN, "disabled": COLOR_MUTED,
                         "pausado": COLOR_MUTED}.get(status, COLOR_YELLOW)
                display.draw_text(202, y, text[:40], color, 1)
                display.draw_text(202, y + 9, text[40:80], color, 1)
            gps_status, gps = sensor_status(summary, "gps", now)
            display.draw_text(202, 156, ("GPS: " + gps)[:43], COLOR_GREEN if gps_status == "ok" else COLOR_YELLOW, 1)
            display.draw_text(202, 173, "A inicia/pausa  ESQ encerra", COLOR_TEXT, 1)
        display.draw_text_centered(198, message[:72], COLOR_YELLOW, 1)
        display.draw_text_centered(212, "DIR alvo  CIMA/BAIXO telas  B voltar", COLOR_TEXT, 1)
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
            display.draw_text(20, 129, "Cuidado + vinculo %d / %d" % status["care"], COLOR_TEXT, 1)
            display.draw_text(20, 145, "Bem-estar %d / %d" % status["wellness"], COLOR_TEXT, 1)
        hint = "Escolha a linha em Geracoes / Ovos > Evolucao" if state.branch_pending else "Coleta valida: +1 vinculo a cada 10 min."
        display.draw_text(20, 171, hint, COLOR_MUTED, 1)
        display.draw_text_centered(205, "A ou B volta", COLOR_TEXT, 1)
        display.flip()

    def generations(self, state, tab, selected, message="", confirm="", frame_index=0):
        display = self.display
        display.clear(COLOR_BG)
        self._header("GERACOES", state)
        _panel(display, 8, 28, 464, 164)
        tabs = ("VIDA", "OVO SUCESSOR", "MEMORIAL", "EVOLUCAO")
        display.draw_text(20, 39, "%d/4 %s" % (tab + 1, tabs[tab]), COLOR_CYAN, 1)
        if confirm:
            line_id = state.egg_line_id if confirm == "birth" else state.branch_offers[selected % len(state.branch_offers)]
            creature = self.catalog.creature_for_stage(line_id, 0 if confirm == "birth" else 2)
            display.draw_text(20, 66, "Confirmar nascimento?" if confirm == "birth" else "Confirmar esta evolucao?", COLOR_YELLOW, 1)
            display.draw_text(20, 88, creature["name"], COLOR_TEXT, 1)
            display.draw_text(20, 112, "Novo pet: ovo e nivel 1." if confirm == "birth" else "Esta linha segue ate a forma especial.", COLOR_TEXT, 1)
            display.draw_text(20, 132, "Treinador, bestiario e memorial preservados.", COLOR_MUTED, 1)
            draw_sprite(display, creature, 375, 65, scale=2, frame_index=frame_index)
            display.draw_text(20, 171, "A confirma  B cancela", COLOR_CYAN, 1)
        elif tab == 0:
            creature = self.catalog.creature(state.creature_id)
            display.draw_text(20, 63, "Geracao %d | %s" % (state.generation, creature["name"]), COLOR_TEXT, 1)
            display.draw_text(20, 83, lifecycle.age_label(state), COLOR_YELLOW, 1)
            display.draw_text(20, 103, "Coleta nesta vida: %dh %02dmin" % (state.life_active_seconds // 3600, state.life_active_seconds // 60 % 60), COLOR_TEXT, 1)
            remaining = max(0, lifecycle.ADULT_LIFETIME - state.adult_active_seconds)
            text = "Vida adulta restante: %dh %02dmin" % (remaining // 3600, remaining // 60 % 60) if state.stage >= 3 else "Relogio adulto comeca na fase adulta."
            display.draw_text(20, 123, text, COLOR_TEXT, 1)
            display.draw_text(20, 144, "Linhas nascidas %d/50 | Ciclos concluidos %d" % (len(state.hatched_lines), state.memorial_total), COLOR_MUTED, 1)
            display.draw_text(20, 171, "A abre o ovo sucessor", COLOR_CYAN, 1)
        elif tab == 1:
            if state.egg_line_id:
                line = self.catalog.evolution_line(state.egg_line_id)
                display.draw_text(20, 66, "Ovo escolhido: " + line["name"], COLOR_TEXT, 1)
                minutes = max(0, lifecycle.EGG_INCUBATION - state.egg_incubation_seconds + 59) // 60
                display.draw_text(20, 91, "Incubacao: pronto" if not minutes else "Incubacao: faltam %d min de coleta" % minutes, COLOR_YELLOW, 1)
                display.draw_text(20, 121, "Heranca: uma afinidade inicial, sem XP extra.", COLOR_MUTED, 1)
                text = "A inicia a proxima geracao" if lifecycle.birth_ready(state) else "Nascimento apos o fim do ciclo atual." if not minutes else "Continue explorando para incubar."
                display.draw_text(20, 162, text, COLOR_CYAN, 1)
            elif state.egg_offers:
                display.draw_text(20, 64, "Escolha um ovo para a proxima geracao:", COLOR_TEXT, 1)
                for index, line_id in enumerate(state.egg_offers):
                    line = self.catalog.evolution_line(line_id)
                    family = self.catalog.family_by_id[line["family_id"]]
                    y = 91 + index * 23
                    if index == selected % len(state.egg_offers):
                        display.fill_rect(17, y - 3, 446, 17, COLOR_PANEL_ALT)
                    display.draw_text(22, y, ("> " if index == selected % len(state.egg_offers) else "  ") + family["name"] + " / " + line["name"], COLOR_CYAN, 1)
                display.draw_text(20, 174, "A escolhe; depois incuba por 20 min de coleta.", COLOR_MUTED, 1)
            else:
                minutes = max(0, lifecycle.EGG_PREPARATION - state.egg_activity_seconds + 59) // 60
                display.draw_text(20, 74, "Proximo ovo: faltam %d min de coleta valida" % minutes, COLOR_TEXT, 1)
                display.draw_text(20, 103, "Rotas conhecidas tambem contam.", COLOR_MUTED, 1)
                display.draw_text(20, 132, "O progresso fica salvo entre expedicoes.", COLOR_MUTED, 1)
        elif tab == 2:
            if not state.memorial:
                display.draw_text(20, 76, "Cada companheiro deixara sua historia aqui.", COLOR_TEXT, 1)
            else:
                entry = list(reversed(state.memorial))[selected % len(state.memorial)]
                creature = self.catalog.creature(entry["creature_id"])
                display.draw_text(20, 64, "Geracao %d: %s" % (entry["generation"], creature["name"]), COLOR_TEXT, 1)
                display.draw_text(20, 86, "Nivel %d | XP %d" % (entry["level"], entry["xp"]), COLOR_GREEN, 1)
                display.draw_text(20, 108, "Jornada %.1fh | %.2f km" % (entry["active_seconds"] / 3600, entry["distance_m"] / 1000), COLOR_TEXT, 1)
                display.draw_text(20, 130, "Descobertas/revisitas %d | Medalhas %d" % (entry["contacts"], len(entry["medals"])), COLOR_MUTED, 1)
                display.draw_text(20, 153, "Legado: " + lifecycle.PROFILE_LABELS[entry["trait"]], COLOR_YELLOW, 1)
                display.draw_text(20, 176, "Registro %d/%d | CIMA/BAIXO navega" % (selected % len(state.memorial) + 1, len(state.memorial)), COLOR_MUTED, 1)
        else:
            if state.branch_pending:
                display.draw_text(20, 64, "Escolha a linha da fase jovem:", COLOR_TEXT, 1)
                for index, line_id in enumerate(state.branch_offers):
                    line = self.catalog.evolution_line(line_id)
                    y = 91 + index * 23
                    if index == selected % len(state.branch_offers):
                        display.fill_rect(17, y - 3, 446, 17, COLOR_PANEL_ALT)
                    profile = lifecycle.PROFILE_LABELS[lifecycle.LINE_PROFILES[line["family_line_index"]]]
                    display.draw_text(22, y, ("> " if index == selected % len(state.branch_offers) else "  ") + line["name"] + " | " + profile, COLOR_CYAN, 1)
                display.draw_text(20, 174, "A mostra a confirmacao; todas estao acessiveis.", COLOR_MUTED, 1)
            else:
                line = self.catalog.evolution_line(state.line_id)
                display.draw_text(20, 72, "Linha atual: " + line["name"], COLOR_TEXT, 1)
                text = "Linha ja definida para este companheiro." if state.branch_locked else "A escolha abre ao evoluir de filhote a jovem."
                display.draw_text(20, 105, text, COLOR_MUTED, 1)
                display.draw_text(20, 138, "Exploracao, sintonia e cuidado sugerem opcoes.", COLOR_MUTED, 1)
        display.draw_text_centered(198, message[:72], COLOR_YELLOW, 1)
        footer = "A confirma  B cancela" if confirm else "ESQ/DIR abas  CIMA/BAIXO escolhe  A acao  B volta"
        display.draw_text_centered(212, footer, COLOR_TEXT, 1)
        display.flip()

    def network(self, state, selected, message, busy=False, confirm=False):
        display = self.display
        display.clear(COLOR_BG)
        self._header("REDES / LABORATORIO", state)
        _panel(display, 8, 28, 464, 164)
        display.draw_text(20, 38, "Fila avulsa: %d/500  XP exploracao: %d" % (
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

    def wdgwars(self, state, selected, mode, status, busy=False, screen="wdgwars"):
        display = self.display
        display.clear(COLOR_BG)
        self._header("WDGWARS", state)
        _panel(display, 8, 28, 464, 164)
        if screen == "wdgwars_overview":
            overview = status.get("overview", {})
            display.draw_text(20, 39, "TODAS AS EXPEDICOES + FILA AVULSA", COLOR_CYAN, 1)
            total = overview.get("pending")
            display.draw_text(20, 58, "Prontos para enviar: %s" % (total if total is not None else "desconhecido"), COLOR_YELLOW, 1)
            display.draw_text(20, 75, "CSV: %s  Fila extra: %s  Saidas: %s" % (
                overview.get("csv_records", "?"), overview.get("queue_records", "?"),
                overview.get("pending_expeditions", "?")), COLOR_TEXT, 1)
            last = overview.get("last_confirmed")
            stamp = time.strftime("%d/%m/%Y %H:%M UTC", time.gmtime(last["at"])) if last else "sem recibo local" if overview else "nao consultado"
            display.draw_text(20, 94, "Ultimo lote aceito: " + stamp, COLOR_GREEN if last else COLOR_MUTED, 1)
            display.draw_text(20, 111, "Invalidos:%s Incompletos:%s Erros:%s" % (
                overview.get("skipped", "?"), overview.get("incomplete", "?"), overview.get("source_errors", "?")), COLOR_MUTED, 1)
            tips = overview.get("guidance", guidance(status.get("status", "ready")))
            for row, tip in enumerate(tips):
                display.draw_text(20, 135 + row * 17, tip[:72], COLOR_TEXT, 1)
            if overview.get("at"):
                stamp = time.strftime("%H:%M:%S UTC", time.gmtime(overview["at"]))
                display.draw_text(20, 176, "Consulta local: " + stamp, COLOR_MUTED, 1)
        elif screen == "wdgwars_confirm":
            source = "Expedicoes completas + fila" if mode == "expeditions" else "Fila rapida" if mode == "queue" else "Guardar lote e liberar fila" if mode == "archive" else "Repetir somente o lote pendente"
            display.draw_text(20, 42, source, COLOR_CYAN, 1)
            if mode == "archive":
                display.draw_text(20, 68, "Guarda o lote sem confirmar recebimento.", COLOR_YELLOW, 1)
                display.draw_text(20, 88, "Arquivos originais permanecem intactos.", COLOR_TEXT, 1)
                display.draw_text(20, 108, "Nao cancela processamento remoto.", COLOR_TEXT, 1)
                display.draw_text(20, 134, "Futuro envio pode repetir registros.", COLOR_YELLOW, 1)
            else:
                display.draw_text(20, 68, "Enviar nomes, MACs, sinal e GPS?", COLOR_YELLOW, 1)
                display.draw_text(20, 88, "Somente CSVs de descobertas do Hackomon.", COLOR_TEXT, 1)
                display.draw_text(20, 108, "Capturas e senhas ficam no dispositivo.", COLOR_TEXT, 1)
            if mode == "retry":
                display.draw_text(20, 134, "Pode repetir registros ja recebidos pelo servidor.", COLOR_YELLOW, 1)
            display.draw_text(20, 164, "A confirma  B cancela", COLOR_CYAN, 1)
        elif screen == "wdgwars_history":
            display.draw_text(20, 40, "ULTIMOS LOTES (historico local)", COLOR_CYAN, 1)
            entries = list(reversed(status.get("history", [])))[selected:selected + 6]
            if not entries:
                display.draw_text(20, 71, "Nenhum recibo local disponivel", COLOR_MUTED, 1)
            for row, entry in enumerate(entries):
                stamp = time.strftime("%d/%m %H:%M", time.gmtime(entry.get("at", 0)))
                labels = {"confirmed": "aceito", "uncertain": "sem confirmacao", "pending_remote": "enfileirado",
                          "rate_limited": "aguardar", "rejected": "recusado", "skipped_local": "ignorado local"}
                label = labels.get(entry.get("status"), str(entry.get("status", "")))
                counts = entry.get("counters", {})
                text = "%s UTC %s %s N%d I%s G%d B%d L%d" % (stamp, label[:12], str(entry.get("source", ""))[:6],
                    entry.get("records", 0), counts.get("imported", "?"), counts.get("no_gps", 0),
                    counts.get("bad_rows", 0), entry.get("skipped", 0))
                display.draw_text(20, 65 + row * 18, text[:72], COLOR_TEXT, 1)
            display.draw_text(20, 177, "N envio I importado G semGPS B invalido L local", COLOR_MUTED, 1)
        else:
            user = status.get("account", {}).get("username", "ainda nao validada")
            display.draw_text(20, 39, "Conta: " + user[:40], COLOR_CYAN, 1)
            options = ("Sincronizar expedicoes + fila", "Enviar somente fila rapida", "Validar chave e consultar conta",
                       "Historico local de envios", "Repetir envio incerto", "Guardar lote pendente e liberar fila")
            for index, label in enumerate(options):
                y = 59 + index * 16
                if index == selected:
                    display.fill_rect(17, y - 3, 446, 15, COLOR_PANEL_ALT)
                display.draw_text(22, y, ("> " if selected == index else "  ") + label,
                                  COLOR_CYAN if selected == index else COLOR_TEXT, 1)
            if status.get("status") == "account_ok":
                account = status.get("account", {})
                display.draw_text(20, 157, "Conta: Wi-Fi %s  BLE %s" % (account.get("wifi", "n/d"), account.get("ble", "n/d")), COLOR_GREEN, 1)
                display.draw_text(20, 175, "Total informado: %s" % account.get("total", "n/d"), COLOR_MUTED, 1)
            else:
                display.draw_text(20, 157, "Envio aceito: %d itens / %d lotes" % (status.get("sent", 0), status.get("batches", 0)), COLOR_GREEN, 1)
                counts = status.get("counters", {})
                display.draw_text(20, 175, "Importados:%s SemGPS:%d Invalidos:%d" % (
                    counts.get("imported", "n/d"), counts.get("no_gps", 0), counts.get("bad_rows", 0)), COLOR_MUTED, 1)
        display.draw_text_centered(198, status.get("message", "")[:72], COLOR_YELLOW, 1)
        footer = ("B interrompe apos a etapa atual" if busy else
                  "A envia  ESQ atualiza  B menu" if screen == "wdgwars_overview" else
                  "CIMA/BAIXO pagina  B volta" if screen == "wdgwars_history" else
                  "A confirma  B cancela" if screen == "wdgwars_confirm" else
                  "A confirma  CIMA/BAIXO escolhe  DIR painel  B volta")
        display.draw_text_centered(212, footer, COLOR_TEXT, 1)
        display.flip()


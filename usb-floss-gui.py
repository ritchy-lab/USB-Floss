# ============================================================
# USB-Floss — Interface graphique (version simple et compacte)
# © 2026 Richard Cogne — Tous droits réservés
# made by ritchy
# ============================================================

import logging
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import webbrowser

import customtkinter as ctk
from PIL import Image

from usbfloss import (
    JUNK_DIRS,
    MAX_VOLUME_SIZE_GB,
    delete,
    format_size,
    list_volumes,
    scan,
)

log = logging.getLogger("usbfloss.gui")

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

if sys.platform == "darwin":
    FONT_MAIN = "SF Pro Display"
    FONT_MONO = "Menlo"
elif sys.platform == "win32":
    FONT_MAIN = "Segoe UI"
    FONT_MONO = "Consolas"
else:
    FONT_MAIN = "DejaVu Sans"
    FONT_MONO = "DejaVu Sans Mono"

# Palette
BG_MAIN = "#000000"
BG_CARD = "#0F161C"
CYAN = "#00F0FF"
CYAN_DARK = "#00A8B8"
CYAN_BRIGHT = "#3BFCFF"
CYAN_HOVER = "#23A7C8"
ACCENT = "#3DDFA0"
LINK_COLOR = "#7FE0E8"
WARN = "#FFA500"
RED = "#D22D2D"
TEXT_WHITE = "#FFFFFF"
TEXT_GREY = "#8A9AA9"
TEXT_DIM = "#5A6A78"
BTN_DISABLED = "#3A4A55"

# Fenêtre
WIN_W = 480
PAD = 16
LOGO_WIDTH = WIN_W          # le bandeau occupe toute la largeur
LIST_HEIGHT = 150           # hauteur de la liste de résultats

# Rythme des vérifications
VOLUME_CHECK_INTERVAL = 2000     # détection des volumes
RESCAN_INTERVAL = 15000          # re-scan maximal (clé lente)
RESCAN_INTERVAL_MIN = 2000       # re-scan minimal (clé rapide : réaction en 2 s)
RESCAN_FACTEUR = 25              # marge : 25 x la durée du dernier scan
QUEUE_POLL_INTERVAL = 100        # lecture des résultats des fils d'exécution
EJECT_TIMEOUT = 30
MAX_ROWS = 2000                  # lignes affichées au maximum
RESULTAT_DUREE = 6               # un message de résultat reste affiché 6 s

# Dossiers gérés par macOS : signalés mais jamais supprimés.
# La liste vient du cœur (usbfloss.JUNK_DIRS) pour ne pas la recopier.
PROTECTED_NAMES = set(JUNK_DIRS)

APP_VERSION = "1.3"
GITHUB_URL = "https://github.com/ritchy-lab/USB-Floss"
KO_FI_URL = "https://ko-fi.com/ritchy_lab"
CURSOR_HAND = "pointinghand" if sys.platform == "darwin" else "hand2"

def _couleur_moyenne(img, boite):
    """Couleur moyenne d'une zone de l'image (pour fondre un widget dedans)."""
    try:
        zone = img.crop(boite).convert("RGB")
        px = list(zone.getdata())
        n = len(px)
        r = sum(p[0] for p in px) // n
        v = sum(p[1] for p in px) // n
        b = sum(p[2] for p in px) // n
        return f"#{r:02X}{v:02X}{b:02X}"
    except Exception:
        return BG_MAIN


def _langue_systeme():
    """« fr » si le Mac est en français, « en » dans tous les autres cas."""
    brut = ""
    if sys.platform == "darwin":
        try:
            brut = subprocess.run(
                ["defaults", "read", "-g", "AppleLanguages"],
                capture_output=True, text=True, timeout=5,
            ).stdout
        except Exception:
            brut = ""
    if not brut:
        brut = os.environ.get("LANG") or os.environ.get("LC_ALL") or ""
    trouve = re.search(r'"([^"]+)"', brut)      # « fr-FR » dans la liste des langues
    code = trouve.group(1) if trouve else brut
    return "fr" if code[:2].lower() == "fr" else "en"


LANGUE = _langue_systeme()

TEXTES = {
    "fr": {
        "attente": "En attente d'un volume…",
        "aucun_volume": "Aucun volume détecté",
        "aucun_volume_point": "Aucun volume détecté.",
        "analyse": "Analyse en cours…",
        "trouves": "{n} élément(s) trouvé(s)",
        "que_proteges": "Rien à nettoyer : que des dossiers protégés.",
        "propre": "Aucun fichier parasite. La clé est propre.",
        "nettoyage": "Nettoyage en cours…",
        "supprimes": "{ok} élément(s) supprimé(s) ✓",
        "echecs": "{ok} supprimé(s), {ko} échec(s)",
        "erreur_suppression": "Erreur pendant la suppression : {err}",
        "nettoyer": "Nettoyer",
        "nettoyer_ejecter": "Nettoyer et éjecter",
        "eject_non_pris_en_charge": "Éjection non prise en charge sur ce système.",
        "eject_delai": "La clé ne répond pas (délai de {n} s dépassé).",
        "eject_impossible_detail": "Éjection impossible : {err}",
        "eject_bloquee": "Une application bloque la clé : ferme-la pour la libérer.",
        "eject_deja_retiree": "La clé a déjà été retirée.",
        "eject_plus_montee": "La clé n'est plus montée.",
        "eject_sans_reponse": "La clé ne répond pas.",
        "eject_impossible_brut": "Éjection impossible.\n{extrait}",
        "eject_impossible": "Éjection impossible.",
        "soutenir_titre": "Soutenir le projet",
        "soutenir_question": "Mon utilitaire te sert ou te plaît ?",
        "soutenir_cafe": "Paye-moi un café  ☕",
        "soutenir_oui": "Oui",
        "soutenir_plus_tard": "Une prochaine fois",
        "aide_titre": "À propos — USB-Floss",
        "fermer": "Fermer",
    },
    "en": {
        "attente": "Waiting for a drive…",
        "aucun_volume": "No USB drive detected",
        "aucun_volume_point": "No USB drive detected.",
        "analyse": "Scanning…",
        "trouves": "{n} item(s) found",
        "que_proteges": "Nothing to clean: only protected folders.",
        "propre": "No junk found. This drive is clean.",
        "nettoyage": "Cleaning…",
        "supprimes": "{ok} item(s) removed ✓",
        "echecs": "{ok} removed, {ko} failed",
        "erreur_suppression": "Error while deleting: {err}",
        "nettoyer": "Clean",
        "nettoyer_ejecter": "Clean and eject",
        "eject_non_pris_en_charge": "Ejecting is not supported on this system.",
        "eject_delai": "The drive is not responding ({n} s timeout).",
        "eject_impossible_detail": "Could not eject: {err}",
        "eject_bloquee": "An application is using the drive: close it to release it.",
        "eject_deja_retiree": "The drive has already been removed.",
        "eject_plus_montee": "The drive is no longer mounted.",
        "eject_sans_reponse": "The drive is not responding.",
        "eject_impossible_brut": "Could not eject.\n{extrait}",
        "eject_impossible": "Could not eject.",
        "soutenir_titre": "Support the project",
        "soutenir_question": "Is this little tool useful to you?",
        "soutenir_cafe": "Buy me a coffee  ☕",
        "soutenir_oui": "Yes",
        "soutenir_plus_tard": "Maybe next time",
        "aide_titre": "About — USB-Floss",
        "fermer": "Close",
    },
}


def TR(cle, **valeurs):
    """Texte dans la langue du système (l'anglais sert de secours)."""
    texte = TEXTES[LANGUE].get(cle) or TEXTES["en"].get(cle) or cle
    return texte.format(**valeurs) if valeurs else texte


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(SCRIPT_DIR, "logo.png")

HELP_CONTENT = {
    "fr": [
        ("title", "USB-Floss"),
        ("text", f"Version {APP_VERSION} — la version simple"),
        ("space", ""),
        ("text", "Nettoie une clé USB des fichiers inutiles laissés"),
        ("text", "par macOS, Windows ou Linux."),
        ("space", ""),
        ("title2", "Comment l'utiliser"),
        ("bullet", "1. Branche une clé USB."),
        ("bullet", "2. Elle apparaît en haut, l'analyse se lance seule."),
        ("bullet", "3. Clique sur Nettoyer."),
        ("space", ""),
        ("title2", "Fichiers ignorés"),
        ("text", "Certains dossiers gérés par macOS (.Spotlight-V100,"),
        ("text", ".Trashes, .fseventsd) sont marqués « ignoré » et laissés"),
        ("text", "en place : ils ne gênent pas."),
        ("space", ""),
        ("title2", "Limite de taille"),
        ("text", f"Seuls les volumes de moins de {MAX_VOLUME_SIZE_GB} Go sont"),
        ("text", "proposés automatiquement."),
        ("space", ""),
        ("sep", ""),
        ("donate", "☕  Soutenir le projet"),
        ("credit", f"© 2026 — ritchy-lab — version {APP_VERSION}"),
        ("link", GITHUB_URL.replace("https://", "")),
    ],
    "en": [
        ("title", "USB-Floss"),
        ("text", f"Version {APP_VERSION} — the simple one"),
        ("space", ""),
        ("text", "Cleans a USB drive of the useless files left behind"),
        ("text", "by macOS, Windows and Linux."),
        ("space", ""),
        ("title2", "How to use it"),
        ("bullet", "1. Plug in a USB drive."),
        ("bullet", "2. It shows up at the top and the scan starts by itself."),
        ("bullet", "3. Click Clean."),
        ("space", ""),
        ("title2", "Ignored files"),
        ("text", "Some folders managed by macOS (.Spotlight-V100,"),
        ("text", ".Trashes, .fseventsd) are marked \u201cignored\u201d and left"),
        ("text", "in place: they are harmless."),
        ("space", ""),
        ("title2", "Size limit"),
        ("text", f"Only drives smaller than {MAX_VOLUME_SIZE_GB} GB are"),
        ("text", "offered automatically."),
        ("space", ""),
        ("sep", ""),
        ("donate", "☕  Support the project"),
        ("credit", f"© 2026 — ritchy-lab — version {APP_VERSION}"),
        ("link", GITHUB_URL.replace("https://", "")),
    ],
}


# ------------------------------------------------------------------
# Application
# ------------------------------------------------------------------
class USBFlossApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("USB-Floss")
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)

        # --- état ---
        self.volumes = []
        self.current_volume = None
        self.all_junk = []
        self.current_junk = []
        self._last_volumes_state = None
        self._last_junk_signature = None
        self._last_scan_duration = None
        self._results = queue.Queue()
        self._scan_running = False
        self._scan_pending = False
        self._busy = False
        self._closing = False
        self._logo_image = None
        self._help_popup = None
        self._donate_popup = None
        self._resultat = None
        self._resultat_temps = 0.0
        self._survol_nettoyer = False
        self._fond_bouton = BG_MAIN
        # polices mesurables (pour dimensionner les canvas au texte)
        self._font_vol = tkfont.Font(font=(FONT_MAIN, 13, "italic"))
        self._font_eject = tkfont.Font(font=(FONT_MAIN, 13))
        self._font_help = tkfont.Font(font=(FONT_MAIN, 13, "bold"))
        self._vol_texte = TR("aucun_volume")
        self._vol_survol = False
        self._eject_survol = False
        self._help_survol = False
        self._after_volumes = None
        self._after_rescan = None
        self._after_poll = None

        self._eject = False

        self._build_banner()
        self._build_controls()
        self._build_results()
        self._build_footer()

        # La fenêtre prend juste la hauteur nécessaire : compacte.
        self.update_idletasks()
        hauteur = max(self.winfo_reqheight(), 360)
        x = (self.winfo_screenwidth() - WIN_W) // 2
        y = (self.winfo_screenheight() - hauteur) // 3
        self.geometry(f"{WIN_W}x{hauteur}+{x}+{y}")

        self._after_poll = self.after(100, self._poll_results)
        self._after_volumes = self.after(100, self._tick_volumes)
        self._after_rescan = self.after(100, self._tick_rescan)

    def destroy(self):
        """On ferme les fenêtres secondaires, puis on arrête les boucles."""
        self._closing = True
        for popup in (self._help_popup, self._donate_popup):
            if popup is not None and popup.winfo_exists():
                try:
                    popup.destroy()
                except tk.TclError:
                    pass
        for ident in (self._after_volumes, self._after_rescan, self._after_poll):
            if ident:
                try:
                    self.after_cancel(ident)
                except Exception:
                    pass
        super().destroy()

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------
    def _build_banner(self):
        cadre = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        cadre.pack(fill="x")

        if os.path.exists(LOGO_PATH):
            try:
                img = Image.open(LOGO_PATH)
                taille = (LOGO_WIDTH, int(LOGO_WIDTH * img.height / img.width))
                img = img.resize(taille, Image.LANCZOS)
                self._logo_image = ctk.CTkImage(
                    light_image=img, dark_image=img, size=taille)
                ctk.CTkLabel(cadre, image=self._logo_image, text="").pack(fill="x")
                # Le bouton « ? » n'a pas de fond à lui : on prend la couleur du
                # bandeau juste derrière, pour qu'il s'y fonde au lieu d'un rond noir.
                self._fond_bouton = _couleur_moyenne(img, (2, 4, 48, 48))
            except Exception as e:
                log.warning("Erreur chargement logo : %s", e)

        if self._logo_image is None:
            ctk.CTkLabel(
                cadre, text="USB-Floss",
                font=(FONT_MAIN, 26, "bold"), text_color=CYAN,
            ).pack(pady=24)

        # Le « ? » est dessiné dans un canvas : un canvas garantit un cercle
        # parfaitement rond et un texte centré au pixel (un bouton CTk, lui,
        # s'étire et arrondit mal ses coins).
        self.help_canvas = tk.Canvas(
            cadre, width=26, height=26, bg=self._fond_bouton,
            bd=0, highlightthickness=0, cursor=CURSOR_HAND,
        )
        self.help_canvas.place(x=10, y=8, anchor="nw")
        self.help_canvas.bind("<Button-1>", lambda e: self._open_help())
        self.help_canvas.bind("<Enter>", lambda e: self._help_hover(True))
        self.help_canvas.bind("<Leave>", lambda e: self._help_hover(False))
        self._draw_help()

    def _build_controls(self):
        cadre = ctk.CTkFrame(self, fg_color="transparent")
        cadre.pack(fill="x", padx=PAD, pady=(0, 8))

        # Cercle et texte sont dessinés dans le MÊME canvas, sur la même ligne
        # de centre : c'est le seul moyen d'avoir un alignement exact, un pack
        # de widgets alignant les textes sur leur boîte (donc vers le bas).
        self.vol_canvas = tk.Canvas(cadre, height=18, bg=BG_MAIN, bd=0,
                                    highlightthickness=0, cursor=CURSOR_HAND)
        self.vol_canvas.pack(side="left")
        self.vol_canvas.bind("<Button-1>", lambda e: self._open_volume_menu())
        self.vol_canvas.bind("<Enter>", lambda e: self._vol_hover(True))
        self.vol_canvas.bind("<Leave>", lambda e: self._vol_hover(False))

        self.eject_canvas = tk.Canvas(cadre, height=18, bg=BG_MAIN, bd=0,
                                      highlightthickness=0, cursor=CURSOR_HAND)
        self.eject_canvas.pack(side="right")
        self.eject_canvas.bind("<Button-1>", lambda e: self._toggle_eject())
        self.eject_canvas.bind("<Enter>", lambda e: self._eject_hover(True))
        self.eject_canvas.bind("<Leave>", lambda e: self._eject_hover(False))

        self._draw_volume()
        self._draw_eject()

    def _build_results(self):
        self.panel = ctk.CTkFrame(
            self, fg_color=BG_CARD, corner_radius=12,
            border_color=CYAN_DARK, border_width=1,
        )
        self.panel.pack(fill="both", expand=True, padx=PAD, pady=(0, 10))

        self.message = ctk.CTkLabel(
            self.panel, text=TR("attente"),
            font=(FONT_MAIN, 12, "italic"), text_color=ACCENT, anchor="w",
        )
        self.message.pack(fill="x", padx=12, pady=(10, 2))

        self.liste = ctk.CTkTextbox(
            self.panel, fg_color="transparent", text_color=TEXT_WHITE,
            font=(FONT_MONO, 11), wrap="none", height=LIST_HEIGHT,
            border_width=0, corner_radius=0,
            scrollbar_button_color=CYAN_DARK,
            scrollbar_button_hover_color=CYAN,
        )
        self.liste.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.liste.tag_config("ignored", foreground=TEXT_DIM)
        self.liste.configure(state="disabled")

    def _build_footer(self):
        pied = ctk.CTkFrame(self, fg_color="transparent")
        pied.pack(fill="x", padx=PAD, pady=(0, 12))

        self.btn_clean = ctk.CTkButton(
            pied, text=TR("nettoyer"), command=self.run_clean,
            font=(FONT_MAIN, 13, "bold"), width=104, height=32,
            corner_radius=16, fg_color="transparent",
            border_color=BTN_DISABLED, border_width=1,
            text_color=TEXT_WHITE, hover_color=CYAN_HOVER,
            state="disabled",
        )
        self.btn_clean.pack()
        self._bind_hover(self.btn_clean,
                         lambda: self._set_survol_nettoyer(True),
                         lambda: self._set_survol_nettoyer(False))

        self.signature = ctk.CTkLabel(
            pied, text="ritchy-lab", font=(FONT_MAIN, 12), text_color=TEXT_DIM,
        )
        self.signature.place(relx=1.0, rely=0.5, anchor="e")
        self.signature.bind("<Button-1>", lambda e: self._open_donate())
        self.signature.bind(
            "<Enter>", lambda e: self.signature.configure(text_color=CYAN))
        self.signature.bind(
            "<Leave>", lambda e: self.signature.configure(text_color=TEXT_DIM))

    def _set_survol_nettoyer(self, actif):
        self._survol_nettoyer = actif
        self._refresh_clean_button()

    def _refresh_clean_button(self):
        """Style du bouton selon son état et le survol.

        Un CTkButton à fond transparent n'a aucun survol visible : le
        hover_color ne s'applique qu'au remplissage. On l'éclaircit donc
        nous-mêmes (fond bleu nuit + contour cyan) quand la souris passe.
        """
        actif = self.btn_clean.cget("state") == "normal"
        if actif and self._survol_nettoyer:
            self.btn_clean.configure(
                fg_color="#123240", border_color=CYAN_BRIGHT, text_color=CYAN)
        elif actif:
            self.btn_clean.configure(
                fg_color="transparent", border_color=CYAN_BRIGHT,
                text_color=TEXT_WHITE)
        else:
            self.btn_clean.configure(
                fg_color="transparent", border_color=BTN_DISABLED,
                text_color=TEXT_GREY)

    # Tous les dessins partagent la ligne de centre y = 9 (canvas de 18 px) :
    # le cercle (boîte 12x12 + contour de 2 = 14 px de diamètre) et le texte
    # (anchor="w" centre verticalement sur y) sont donc parfaitement alignés.
    LIGNE_CENTRE = 9
    ESPACE_CERCLE_TEXTE = 6

    def _draw_help(self):
        c = self.help_canvas
        c.delete("all")
        couleur = CYAN_BRIGHT if self._help_survol else CYAN_DARK
        c.create_oval(1, 1, 25, 25, outline=couleur, width=1)
        c.create_text(14, 14, text="?", font=self._font_help, fill=couleur)

    def _help_hover(self, actif):
        self._help_survol = actif
        self._draw_help()

    def _draw_volume(self):
        c = self.vol_canvas
        c.delete("all")
        couleur = CYAN if self._vol_survol else ACCENT
        y = self.LIGNE_CENTRE
        c.create_oval(1, y - 6, 13, y + 6, outline=couleur, width=2)
        x = 13 + self.ESPACE_CERCLE_TEXTE + 1
        c.configure(width=x + self._font_vol.measure(self._vol_texte))
        c.create_text(x, y, text=self._vol_texte, font=self._font_vol,
                      fill=couleur, anchor="w")

    def _draw_eject(self):
        c = self.eject_canvas
        c.delete("all")
        y = self.LIGNE_CENTRE
        couleur = CYAN if (self._eject or self._eject_survol) else TEXT_GREY
        if self._eject:
            c.create_oval(3, y - 5, 13, y + 5, outline=couleur, fill=couleur,
                          width=1)
        else:
            c.create_oval(1, y - 6, 13, y + 6, outline=couleur, width=2)
        texte = TR("nettoyer_ejecter")
        x = 13 + self.ESPACE_CERCLE_TEXTE + 1
        c.configure(width=x + self._font_eject.measure(texte))
        c.create_text(x, y, text=texte, font=self._font_eject,
                      fill=CYAN if (self._eject or self._eject_survol)
                      else TEXT_GREY,
                      anchor="w")

    def _toggle_eject(self):
        self._eject = not self._eject
        self._draw_eject()

    def _eject_hover(self, actif):
        self._eject_survol = actif
        self._draw_eject()

    def _bind_hover(self, widget, entrer, sortir):
        """Liaison de survol robuste.

        Un CTkButton est un cadre qui contient son propre canvas : c'est ce
        canvas que la souris survole, pas le cadre. Une liaison posée sur le
        bouton seul ne se déclenche donc jamais.
        """
        cibles = [widget]
        for nom in ("_canvas", "_text_label"):
            enfant = getattr(widget, nom, None)
            if enfant is not None:
                cibles.append(enfant)
        for cible in cibles:
            cible.bind("<Enter>", lambda e: entrer(), add="+")
            cible.bind("<Leave>", lambda e: sortir(), add="+")

    def _vol_hover(self, actif):
        self._vol_survol = actif
        self._draw_volume()

    # ------------------------------------------------------------------
    # Détection des volumes
    # ------------------------------------------------------------------
    def _tick_volumes(self):
        if self._closing:
            return
        try:
            self._check_volumes()
        except Exception:
            log.exception("Erreur pendant la détection des volumes")
        finally:
            if not self._closing:
                self._after_volumes = self.after(
                    VOLUME_CHECK_INTERVAL, self._tick_volumes)

    def _check_volumes(self):
        nouveaux = list_volumes()
        etat = tuple((str(v), s) for v, s in nouveaux)

        if etat == self._last_volumes_state:
            return

        self._last_volumes_state = etat
        self.volumes = nouveaux
        self._last_junk_signature = None
        self._set_junk([])

        chemins = [v for v, _ in nouveaux]

        if not chemins:
            self.current_volume = None
            self._set_volume_label(TR("aucun_volume"))
            self._show_message(TR("aucun_volume_point"), italique=True)
            return

        if self.current_volume not in chemins:
            self.current_volume = chemins[0]

        self._set_volume_label(self._volume_text())
        self._request_scan()

    def _volume_text(self):
        if self.current_volume is None:
            return TR("aucun_volume")
        return self.current_volume.name + ("  ▾" if len(self.volumes) > 1 else "")

    def _set_volume_label(self, texte):
        self._vol_texte = texte
        self._draw_volume()

    def _open_volume_menu(self):
        if not self.volumes:
            return
        menu = tk.Menu(self, tearoff=0)
        for vol, taille in self.volumes:
            menu.add_command(
                label=f"{vol.name}  ({format_size(taille)})",
                command=lambda v=vol: self._select_volume(v),
            )
        menu.post(
            self.vol_canvas.winfo_rootx(),
            self.vol_canvas.winfo_rooty() + self.vol_canvas.winfo_height() + 4,
        )

    def _select_volume(self, volume):
        self.current_volume = volume
        self._last_junk_signature = None
        self._set_junk([])
        self._set_volume_label(self._volume_text())
        self._show_message("Analyse en cours…", italique=True)
        self._request_scan()

    # ------------------------------------------------------------------
    # Analyse (dans un fil d'exécution pour ne jamais figer la fenêtre)
    # ------------------------------------------------------------------
    def _tick_rescan(self):
        if self._closing:
            return
        delai = RESCAN_INTERVAL
        try:
            self._request_scan()
            duree = self._last_scan_duration
            if duree is not None:
                delai = int(min(RESCAN_INTERVAL, max(
                    RESCAN_INTERVAL_MIN, duree * 1000 * RESCAN_FACTEUR)))
        except Exception:
            log.exception("Erreur pendant le re-scan")
        finally:
            if not self._closing:
                self._after_rescan = self.after(delai, self._tick_rescan)

    def _request_scan(self):
        if self.current_volume is None or self._busy:
            return
        if self._scan_running:
            self._scan_pending = True
            return
        self._scan_running = True
        self._scan_pending = False
        threading.Thread(
            target=self._scan_worker, args=(self.current_volume,), daemon=True,
        ).start()

    def _scan_worker(self, volume):
        debut = time.perf_counter()
        try:
            junk = scan(volume)
            self._results.put(
                ("scan", volume, junk, None, time.perf_counter() - debut))
        except Exception as e:
            self._results.put(
                ("scan", volume, None, e, time.perf_counter() - debut))

    def _poll_results(self):
        if self._closing:
            return
        try:
            while True:
                try:
                    msg = self._results.get_nowait()
                except queue.Empty:
                    break
                if msg[0] == "scan":
                    self._on_scan_done(*msg[1:])
                elif msg[0] == "clean":
                    self._on_clean_done(*msg[1:])
        except Exception:
            log.exception("Erreur pendant le traitement d'un résultat")
        finally:
            if not self._closing:
                self._after_poll = self.after(QUEUE_POLL_INTERVAL, self._poll_results)

    def _on_scan_done(self, volume, junk, erreur, duree=None):
        self._scan_running = False
        if duree is not None:
            self._last_scan_duration = duree

        if erreur is not None:
            log.warning("Scan impossible sur %s : %s", volume, erreur)
        elif volume == self.current_volume and not self._busy:
            signature = tuple(sorted(str(p.relative_to(volume)) for p in junk))
            if signature != self._last_junk_signature:
                self._last_junk_signature = signature
                self._set_junk(junk)

        if self._scan_pending:
            self._request_scan()

    def _is_protected(self, path):
        return path.name in PROTECTED_NAMES

    def _set_junk(self, junk):
        self.all_junk = list(junk)
        self.current_junk = [p for p in self.all_junk if not self._is_protected(p)]
        self._refresh_status()
        self._fill_list()

    def _refresh_status(self):
        n = len(self.current_junk)

        self.btn_clean.configure(state="normal" if (n and not self._busy) else "disabled")
        self._refresh_clean_button()

        # Un résultat de nettoyage reste affiché quelques secondes : sans ça, le
        # rafraîchissement du compteur effacerait aussitôt « x supprimé(s) ✓ ».
        if self._resultat and time.time() - self._resultat_temps < RESULTAT_DUREE:
            return
        self._resultat = None

        if self.current_volume is None:
            self._show_message(TR("aucun_volume_point"), italique=True)
        elif n:
            self._show_message(TR("trouves", n=n), couleur=CYAN)
        elif self.all_junk:
            self._show_message(TR("que_proteges"),
                               italique=True)
        else:
            self._show_message(TR("propre"),
                               italique=True)

    def _show_resultat(self, texte, couleur):
        self._resultat = texte
        self._resultat_temps = time.time()
        self._show_message(texte, couleur)

    def _show_message(self, texte, couleur=None, italique=False):
        self.message.configure(
            text=texte,
            text_color=couleur or ACCENT,
            font=(FONT_MAIN, 12, "italic") if italique else (FONT_MAIN, 12, "bold"),
        )

    def _fill_list(self):
        volume = self.current_volume
        lignes = []
        ignorees = []
        for path in self.all_junk[:MAX_ROWS]:
            try:
                rel = str(path.relative_to(volume)) if volume else str(path)
            except ValueError:
                rel = str(path)
            if self._is_protected(path):
                lignes.append(f"{rel}    (ignoré)")
                ignorees.append(len(lignes))
            else:
                lignes.append(rel)
        if len(self.all_junk) > MAX_ROWS:
            lignes.append(f"… et {len(self.all_junk) - MAX_ROWS} autre(s)")
            ignorees.append(len(lignes))

        self.liste.configure(state="normal")
        self.liste.delete("1.0", "end")
        if lignes:
            self.liste.insert("end", "\n".join(lignes) + "\n")
        for num in ignorees:
            self.liste.tag_add("ignored", f"{num}.0", f"{num}.end")
        self.liste.configure(state="disabled")

    # ------------------------------------------------------------------
    # Nettoyage
    # ------------------------------------------------------------------
    def run_clean(self):
        if self._busy or not self.current_junk or self.current_volume is None:
            return

        volume = self.current_volume
        junk = list(self.current_junk)
        self._busy = True
        self._show_message(TR("nettoyage"), italique=True)
        self.btn_clean.configure(state="disabled")
        self._refresh_clean_button()
        threading.Thread(
            target=self._clean_worker,
            args=(volume, junk, self._eject),
            daemon=True,
        ).start()

    def _clean_worker(self, volume, junk, ejecter):
        try:
            ok, ko = delete(junk, volume)
        except Exception as e:
            self._results.put(("clean", volume, 0, 0, str(e), None))
            return
        erreur_ejection = self._eject_volume(volume) if ejecter else None
        self._results.put(("clean", volume, ok, ko, None, erreur_ejection))

    def _on_clean_done(self, volume, ok, ko, erreur, erreur_ejection):
        self._busy = False
        self._last_volumes_state = None
        self._last_junk_signature = None
        self._set_junk([])

        if erreur:
            self._show_resultat(TR("erreur_suppression", err=erreur), RED)
        elif ko == 0:
            self._show_resultat(TR("supprimes", ok=ok), ACCENT)
        else:
            self._show_resultat(TR("echecs", ok=ok, ko=ko), WARN)

        if erreur_ejection:
            self._show_resultat(erreur_ejection, WARN)

        try:
            self._check_volumes()
        except Exception:
            log.exception("Erreur pendant la détection des volumes")
        self._refresh_status()
        self._request_scan()

    # ------------------------------------------------------------------
    # Éjection
    # ------------------------------------------------------------------
    def _eject_volume(self, volume):
        if sys.platform != "darwin":
            return TR("eject_non_pris_en_charge")
        try:
            res = subprocess.run(
                ["diskutil", "eject", str(volume)],
                capture_output=True, text=True, timeout=EJECT_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return TR("eject_delai", n=EJECT_TIMEOUT)
        except Exception as e:
            return TR("eject_impossible_detail", err=e)

        if res.returncode != 0:
            return self._translate_eject_error(res.stderr or res.stdout or "")
        return None

    def _translate_eject_error(self, brut):
        bas = brut.lower()
        if "could not be unmounted" in bas or "dissent" in bas:
            return TR("eject_bloquee")
        if "was not found" in bas or "no such file" in bas:
            return TR("eject_deja_retiree")
        if "not mounted" in bas:
            return TR("eject_plus_montee")
        if "timeout" in bas:
            return TR("eject_sans_reponse")
        extrait = brut.strip()[:160]
        return TR("eject_impossible_brut", extrait=extrait) if extrait else TR("eject_impossible")

    # ------------------------------------------------------------------
    # Fenêtre d'aide
    # ------------------------------------------------------------------
    def _open_link(self, url):
        webbrowser.open(url)

    def _open_help(self):
        if self._help_popup is not None and self._help_popup.winfo_exists():
            self._help_popup.lift()
            self._help_popup.focus_force()
            return

        popup = ctk.CTkToplevel(self)
        self._help_popup = popup
        popup.title(TR("aide_titre"))
        popup.resizable(False, False)
        popup.transient(self)
        popup.configure(fg_color=BG_MAIN)
        popup.bind("<Escape>", lambda e: popup.destroy())

        self.update_idletasks()
        largeur, hauteur = 460, 540
        x = self.winfo_x() + (self.winfo_width() - largeur) // 2
        y = self.winfo_y() + (self.winfo_height() - hauteur) // 2
        popup.geometry(f"{largeur}x{hauteur}+{max(x, 0)}+{max(y, 0)}")

        contenu = ctk.CTkScrollableFrame(
            popup, fg_color=BG_CARD, corner_radius=10,
            scrollbar_button_color=CYAN, scrollbar_button_hover_color=CYAN_BRIGHT,
        )
        contenu.pack(fill="both", expand=True, padx=15, pady=(15, 8))

        for kind, txt in HELP_CONTENT[LANGUE]:
            if kind == "space":
                ctk.CTkLabel(contenu, text="", height=6).pack()
            elif kind == "title":
                ctk.CTkLabel(contenu, text=txt, font=(FONT_MAIN, 18, "bold"),
                             text_color=CYAN, anchor="w").pack(fill="x", pady=(4, 2))
            elif kind == "title2":
                ctk.CTkLabel(contenu, text=txt, font=(FONT_MAIN, 14, "bold"),
                             text_color=ACCENT, anchor="w").pack(fill="x", pady=(8, 2))
            elif kind == "bullet":
                ctk.CTkLabel(contenu, text="    " + txt, font=(FONT_MAIN, 12),
                             text_color=TEXT_WHITE, anchor="w",
                             justify="left").pack(fill="x")
            elif kind == "sep":
                ctk.CTkFrame(contenu, height=1, fg_color="#2A3A48").pack(
                    fill="x", pady=8)
            elif kind == "donate":
                lbl = ctk.CTkLabel(contenu, text=txt, font=(FONT_MAIN, 12),
                                   text_color=LINK_COLOR, anchor="center")
                lbl.pack(fill="x", pady=(0, 4))
                lbl.bind("<Button-1>", lambda e: self._open_link(KO_FI_URL))
                self._bind_link(lbl)
            elif kind == "link":
                lbl = ctk.CTkLabel(contenu, text=txt, font=(FONT_MONO, 10),
                                   text_color=LINK_COLOR, anchor="center")
                lbl.pack(fill="x")
                lbl.bind("<Button-1>", lambda e: self._open_link(GITHUB_URL))
                self._bind_link(lbl)
            elif kind == "credit":
                ctk.CTkLabel(contenu, text=txt, font=(FONT_MAIN, 10),
                             text_color=TEXT_GREY, anchor="center").pack(
                    fill="x", pady=(4, 2))
            else:
                ctk.CTkLabel(contenu, text=txt, font=(FONT_MAIN, 12),
                             text_color=TEXT_WHITE, anchor="w",
                             justify="left").pack(fill="x")

        ctk.CTkButton(
            popup, text=TR("fermer"), font=(FONT_MAIN, 13, "bold"),
            width=140, height=36, corner_radius=18, fg_color="transparent",
            border_color=CYAN_BRIGHT, border_width=1, text_color=TEXT_WHITE,
            hover_color=CYAN_HOVER, command=popup.destroy,
        ).pack(pady=(0, 15))

        popup.after(150, lambda: self._grab_popup(popup))

        # customtkinter ne capte la molette que sur certains widgets, et avec une
        # Magic Mouse (pas de molette, défilement très fin) les deltas valent ±1 :
        # on lie donc nous-mêmes toute la fenêtre, et on garde le bon sens même
        # pour un delta minuscule.
        def _molette(evenement):
            try:
                delta = float(evenement.delta)
            except (TypeError, ValueError):
                return
            if delta == 0:
                return
            pas = -delta / 10.0
            if abs(pas) < 1:
                pas = -1.0 if delta > 0 else 1.0
            contenu._parent_canvas.yview_scroll(int(pas), "units")

        def _lier_molette(widget):
            widget.bind("<MouseWheel>", _molette, add="+")
            for enfant in widget.winfo_children():
                _lier_molette(enfant)

        _lier_molette(popup)

        # Filet de sécurité : au clavier, ça marche avec n'importe quelle souris.
        for touche, pas in (("<Up>", -2), ("<Down>", 2), ("<Prior>", -6),
                            ("<Next>", 6), ("<Home>", -200), ("<End>", 200)):
            popup.bind(touche, lambda e, n=pas: contenu._parent_canvas.yview_scroll(n, "units"),
                       add="+")

    def _grab_popup(self, popup):
        if popup is None or not popup.winfo_exists():
            return
        try:
            popup.grab_set()
            popup.focus_set()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Mini fenêtre de soutien (clic sur la signature)
    # ------------------------------------------------------------------
    def _open_donate(self):
        if self._donate_popup is not None and self._donate_popup.winfo_exists():
            self._donate_popup.lift()
            self._donate_popup.focus_force()
            return

        popup = ctk.CTkToplevel(self)
        self._donate_popup = popup
        popup.title(TR("soutenir_titre"))
        popup.resizable(False, False)
        popup.transient(self)
        popup.configure(fg_color=BG_MAIN)
        popup.bind("<Escape>", lambda e: popup.destroy())

        largeur = 380
        ctk.CTkLabel(
            popup, text=TR("soutenir_question"),
            font=(FONT_MAIN, 16, "normal"), text_color=TEXT_WHITE,
            wraplength=largeur - 50, justify="center",
        ).pack(padx=25, pady=(26, 6))
        ctk.CTkLabel(
            popup, text=TR("soutenir_cafe"),
            font=(FONT_MAIN, 14), text_color=LINK_COLOR,
        ).pack()

        boutons = ctk.CTkFrame(popup, fg_color="transparent")
        boutons.pack(pady=(24, 26))

        ctk.CTkButton(
            boutons, text=TR("soutenir_oui"), command=self._donate_oui,
            font=(FONT_MAIN, 13, "bold"), width=96, height=32,
            corner_radius=16, fg_color="transparent",
            border_color=CYAN_BRIGHT, border_width=1,
            text_color=TEXT_WHITE, hover_color="#123240",
        ).pack(side="left", padx=7)
        ctk.CTkButton(
            boutons, text=TR("soutenir_plus_tard"), command=popup.destroy,
            font=(FONT_MAIN, 12), width=170, height=32,
            corner_radius=16, fg_color="transparent",
            border_color=BTN_DISABLED, border_width=1,
            text_color=TEXT_GREY, hover_color="#1A2530",
        ).pack(side="left", padx=7)

        popup.update_idletasks()
        hauteur = popup.winfo_reqheight()
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - largeur) // 2
        y = self.winfo_y() + (self.winfo_height() - hauteur) // 2
        popup.geometry(f"{largeur}x{hauteur}+{max(x, 0)}+{max(y, 0)}")
        popup.after(150, lambda: self._grab_popup(popup))

    def _donate_oui(self):
        self._open_link(KO_FI_URL)
        if self._donate_popup is not None and self._donate_popup.winfo_exists():
            self._donate_popup.destroy()

    def _bind_link(self, widget):
        """Éclaircit un lien au survol (le curseur main n'est pas fiable sur macOS)."""
        widget.bind("<Enter>", lambda e: widget.configure(text_color=TEXT_WHITE))
        widget.bind("<Leave>", lambda e: widget.configure(text_color=LINK_COLOR))
        try:
            widget.configure(cursor=CURSOR_HAND)
        except Exception:
            pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = USBFlossApp()
    app.mainloop()

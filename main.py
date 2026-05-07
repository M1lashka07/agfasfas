import json
import os
import threading
import urllib.parse
import urllib.request
from tkinter import Tk, StringVar, END, messagebox
from tkinter import ttk

FAVORITES_FILE = "favorites.json"
GITHUB_API_URL = "https://api.github.com/search/users"


class GitHubUserFinder:
    def __init__(self, root):
        self.root = root
        self.root.title("GitHub User Finder")
        self.root.geometry("780x520")
        self.root.minsize(700, 450)

        self.search_var = StringVar()
        self.status_var = StringVar(value="Введите имя пользователя GitHub и нажмите «Поиск».")
        self.results = []
        self.favorites = self.load_favorites()

        self.build_ui()
        self.refresh_favorites_list()

    def build_ui(self):
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill="x")

        ttk.Label(top_frame, text="Поиск пользователя GitHub:").pack(side="left")

        search_entry = ttk.Entry(top_frame, textvariable=self.search_var, width=38)
        search_entry.pack(side="left", padx=8)
        search_entry.bind("<Return>", lambda event: self.search_users())

        ttk.Button(top_frame, text="Поиск", command=self.search_users).pack(side="left")
        ttk.Button(top_frame, text="Очистить", command=self.clear_search).pack(side="left", padx=6)

        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)

        results_frame = ttk.LabelFrame(main_frame, text="Результаты поиска", padding=8)
        results_frame.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self.results_list = ttk.Treeview(
            results_frame,
            columns=("login", "url"),
            show="headings",
            selectmode="browse"
        )
        self.results_list.heading("login", text="Login")
        self.results_list.heading("url", text="Профиль")
        self.results_list.column("login", width=160)
        self.results_list.column("url", width=300)
        self.results_list.pack(fill="both", expand=True)

        ttk.Button(
            results_frame,
            text="Добавить в избранное",
            command=self.add_selected_to_favorites
        ).pack(fill="x", pady=(8, 0))

        favorites_frame = ttk.LabelFrame(main_frame, text="Избранные пользователи", padding=8)
        favorites_frame.pack(side="right", fill="both", expand=True, padx=(6, 0))

        self.favorites_list = ttk.Treeview(
            favorites_frame,
            columns=("login", "url"),
            show="headings",
            selectmode="browse"
        )
        self.favorites_list.heading("login", text="Login")
        self.favorites_list.heading("url", text="Профиль")
        self.favorites_list.column("login", width=160)
        self.favorites_list.column("url", width=300)
        self.favorites_list.pack(fill="both", expand=True)

        ttk.Button(
            favorites_frame,
            text="Удалить из избранного",
            command=self.remove_selected_favorite
        ).pack(fill="x", pady=(8, 0))

        status_bar = ttk.Label(self.root, textvariable=self.status_var, padding=8, relief="sunken")
        status_bar.pack(fill="x", side="bottom")

    def validate_query(self):
        query = self.search_var.get().strip()

        if not query:
            messagebox.showwarning("Ошибка ввода", "Поле поиска не должно быть пустым.")
            return None

        return query

    def search_users(self):
        query = self.validate_query()

        if not query:
            return

        self.status_var.set("Идёт поиск...")
        self.set_controls_state("disabled")

        thread = threading.Thread(target=self.search_users_worker, args=(query,), daemon=True)
        thread.start()

    def search_users_worker(self, query):
        try:
            users = self.fetch_users(query)
            self.root.after(0, lambda: self.show_results(users))
        except Exception as error:
            self.root.after(0, lambda: messagebox.showerror("Ошибка API", str(error)))
            self.root.after(0, lambda: self.status_var.set("Ошибка при получении данных."))
        finally:
            self.root.after(0, lambda: self.set_controls_state("normal"))

    def fetch_users(self, query):
        params = urllib.parse.urlencode({
            "q": query,
            "per_page": 10
        })

        url = f"{GITHUB_API_URL}?{params}"

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "GitHub-User-Finder"
        }

        token = os.getenv("GITHUB_TOKEN")

        if token:
            headers["Authorization"] = f"Bearer {token}"

        request = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status != 200:
                raise RuntimeError(f"GitHub API вернул статус {response.status}")

            data = json.loads(response.read().decode("utf-8"))

        return [
            {
                "login": item.get("login", ""),
                "html_url": item.get("html_url", ""),
                "avatar_url": item.get("avatar_url", "")
            }
            for item in data.get("items", [])
        ]

    def show_results(self, users):
        self.results = users
        self.results_list.delete(*self.results_list.get_children())

        for index, user in enumerate(users):
            self.results_list.insert(
                "",
                END,
                iid=str(index),
                values=(user["login"], user["html_url"])
            )

        self.status_var.set(f"Найдено пользователей: {len(users)}")

    def add_selected_to_favorites(self):
        selected = self.results_list.selection()

        if not selected:
            messagebox.showinfo("Нет выбора", "Выберите пользователя из результатов поиска.")
            return

        user = self.results[int(selected[0])]

        exists = any(
            favorite["login"].lower() == user["login"].lower()
            for favorite in self.favorites
        )

        if exists:
            messagebox.showinfo("Уже добавлен", "Этот пользователь уже есть в избранном.")
            return

        self.favorites.append(user)
        self.save_favorites()
        self.refresh_favorites_list()

        self.status_var.set(f"Пользователь {user['login']} добавлен в избранное.")

    def remove_selected_favorite(self):
        selected = self.favorites_list.selection()

        if not selected:
            messagebox.showinfo("Нет выбора", "Выберите пользователя из избранного.")
            return

        index = int(selected[0])
        removed = self.favorites.pop(index)

        self.save_favorites()
        self.refresh_favorites_list()

        self.status_var.set(f"Пользователь {removed['login']} удалён из избранного.")

    def refresh_favorites_list(self):
        self.favorites_list.delete(*self.favorites_list.get_children())

        for index, user in enumerate(self.favorites):
            self.favorites_list.insert(
                "",
                END,
                iid=str(index),
                values=(user["login"], user["html_url"])
            )

    def load_favorites(self):
        if not os.path.exists(FAVORITES_FILE):
            return []

        try:
            with open(FAVORITES_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def save_favorites(self):
        with open(FAVORITES_FILE, "w", encoding="utf-8") as file:
            json.dump(self.favorites, file, ensure_ascii=False, indent=4)

    def clear_search(self):
        self.search_var.set("")
        self.results = []
        self.results_list.delete(*self.results_list.get_children())
        self.status_var.set("Поиск очищен.")

    def set_controls_state(self, state):
        for child in self.root.winfo_children():
            self.set_state_recursive(child, state)

    def set_state_recursive(self, widget, state):
        try:
            if isinstance(widget, ttk.Entry) or isinstance(widget, ttk.Button):
                widget.configure(state=state)
        except Exception:
            pass

        for child in widget.winfo_children():
            self.set_state_recursive(child, state)


if __name__ == "__main__":
    window = Tk()
    app = GitHubUserFinder(window)
    window.mainloop()

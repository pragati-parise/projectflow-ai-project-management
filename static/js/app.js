(function () {
    const root = document.documentElement;
    const themeToggle = document.getElementById("themeToggle");
    const getNextThemeLabel = () =>
        root.getAttribute("data-theme") === "dark" ? "Light Mode" : "Dark Mode";
    const syncThemeButtonLabel = () => {
        if (themeToggle) {
            themeToggle.textContent = getNextThemeLabel();
        }
    };

    const savedTheme = localStorage.getItem("theme");
    if (savedTheme === "dark" || savedTheme === "light") {
        root.setAttribute("data-theme", savedTheme);
    }
    syncThemeButtonLabel();

    if (themeToggle) {
        themeToggle.addEventListener("click", () => {
            const nextTheme = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
            root.setAttribute("data-theme", nextTheme);
            localStorage.setItem("theme", nextTheme);
            syncThemeButtonLabel();
        });
    }
})();

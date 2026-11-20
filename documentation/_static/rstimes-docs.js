window.addEventListener("load", () => {
    for (const button of document.querySelectorAll("button.copybtn")) {
        button.setAttribute("aria-label", "Copy code");
    }
});

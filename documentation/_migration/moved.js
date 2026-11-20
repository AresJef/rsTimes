const destination = new URL(document.querySelector("#documentation-destination").href);
const fragments = JSON.parse(document.querySelector("#documentation-fragments").textContent);
const source = new URL(window.location.href);

if (source.hash) {
    let anchor = source.hash.slice(1);
    try {
        anchor = decodeURIComponent(anchor);
    } catch {
        // A literal malformed fragment can still be carried to the destination.
    }
    if (Object.hasOwn(fragments, anchor)) {
        const target = new URL(fragments[anchor], source.origin);
        destination.pathname = target.pathname;
        destination.hash = target.hash;
    } else if (!destination.hash) {
        destination.hash = source.hash;
    }
}
if (source.search) {
    destination.search = source.search;
}
window.location.replace(destination.href);

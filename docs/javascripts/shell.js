// Pygments' bash lexer leaves commands, flags and arguments as one plain run of text.
// Mark the command word and every flag so shell snippets read at a glance.
// The copy button reads innerText, so the extra spans never reach the clipboard.
(function () {
  var COMMAND = /^[A-Za-z_][\w.\/-]*$/;
  var STARTS_COMMAND = /^(\$\(|\||\|\||&&|;)$/;
  var FLAG = /(^|[\[|(\/])(--?[A-Za-z0-9][\w-]*)/g;

  function span(cls, text) {
    var el = document.createElement("span");
    el.className = cls;
    el.textContent = text;
    return el;
  }

  function mark(code) {
    if (code.dataset.shellMarked) return;
    code.dataset.shellMarked = "1";
    var atCommand = true; // the next word is a command name
    var continued = false; // the line ended with a "\" continuation

    function newLine() {
      atCommand = !continued;
    }

    Array.from(code.childNodes).forEach(function (node) {
      if (node.nodeType === Node.ELEMENT_NODE) {
        var text = node.textContent;
        if (node.tagName === "A") return newLine(); // line-number anchor
        if (node.classList.contains("w")) {
          if (text.indexOf("\n") !== -1) newLine();
          return;
        }
        continued = node.classList.contains("se") && text.trim() === "\\";
        atCommand = STARTS_COMMAND.test(text.trim());
        if (text.indexOf("\n") !== -1) newLine();
        return;
      }
      if (node.nodeType !== Node.TEXT_NODE) return;
      var frag = document.createDocumentFragment();
      node.textContent.split(/(\s+)/).forEach(function (part) {
        if (!part) return;
        if (/^\s+$/.test(part)) {
          if (part.indexOf("\n") !== -1) newLine();
          frag.appendChild(document.createTextNode(part));
          return;
        }
        if (part === "\\") {
          // Plain-text synopses carry their continuations as bare text.
          frag.appendChild(span("se", part));
          atCommand = false;
          continued = true;
          return;
        }
        if (atCommand && COMMAND.test(part)) {
          frag.appendChild(span("gi-cmd", part));
        } else {
          // A flag may sit inside synopsis brackets or an alias pair: [--check], --model/-m.
          var last = 0;
          part.replace(FLAG, function (match, lead, flag, offset) {
            var start = offset + lead.length;
            frag.appendChild(document.createTextNode(part.slice(last, start)));
            frag.appendChild(span("gi-flag", flag));
            last = start + flag.length;
          });
          frag.appendChild(document.createTextNode(part.slice(last)));
        }
        atCommand = false;
        continued = false;
      });
      node.replaceWith(frag);
    });
  }

  function run() {
    document
      .querySelectorAll(".language-bash code, .language-sh code, .language-shell code, .language-zsh code")
      .forEach(mark);
    // Plain-text blocks that open with genimg are command synopses in the CLI reference.
    document.querySelectorAll(".language-text code").forEach(function (code) {
      if (/^genimg\b/.test(code.textContent)) mark(code);
    });
  }

  if (typeof document$ !== "undefined") document$.subscribe(run);
  else document.addEventListener("DOMContentLoaded", run);
})();

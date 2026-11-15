(function () {
  var listEl = document.getElementById("messages");
  var inputEl = document.getElementById("text");
  var errorEl = document.getElementById("error");
  var thinkingEl = document.getElementById("thinking");
  var modelEl = document.getElementById("model");
  var items = [];
  var pending = null;
  var editing = false;
  var token = 0;

  function showError(text) {
    errorEl.textContent = text || "";
  }

  function roleName(role) {
    if (role === "user") return "Вы";
    if (role === "assistant") return "Ответ";
    return role == null ? "" : String(role);
  }

  function rowsFrom(data) {
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.messages)) return data.messages;
    return [];
  }

  function withPending(list) {
    if (!pending) return list;
    var seen = list.some(function (item) {
      return item && String(item.id) === String(pending.id);
    });
    return seen ? list : list.concat([pending]);
  }

  function hasReply(list, id) {
    return list.some(function (item) {
      return item && item.role === "assistant" && String(item.reply_to) === String(id);
    });
  }

  function call(make) {
    return Promise.resolve()
      .then(make)
      .then(function (response) {
        var bad = response.status === 400 || response.status === 404 || response.status === 429 || response.status === 503;
        if (bad) {
          return response.text().then(function (text) {
            var message = "";
            try {
              var data = JSON.parse(text);
              if (data && typeof data.error === "string") message = data.error;
            } catch (err) {
              message = "";
            }
            showError(message);
            return null;
          });
        }
        if (!response.ok) {
          showError("Нет связи с сервисом");
          return null;
        }
        showError("");
        if (response.status === 204) return {};
        return response.text().then(function (text) {
          if (!text) return {};
          return JSON.parse(text);
        });
      })
      .catch(function () {
        showError("Нет связи с сервисом");
        return null;
      });
  }

  function draw() {
    while (listEl.firstChild) listEl.removeChild(listEl.firstChild);
    items.forEach(function (message) {
      var box = document.createElement("div");
      box.className = "message";

      var who = document.createElement("div");
      who.textContent = roleName(message.role);

      var body = document.createElement("div");
      body.className = "text";
      body.textContent = message.content == null ? "" : String(message.content);

      var edit = document.createElement("button");
      edit.type = "button";
      edit.textContent = "Изменить";
      edit.addEventListener("click", function () {
        var field = box.querySelector("textarea");
        if (!field) {
          field = document.createElement("textarea");
          field.value = message.content == null ? "" : String(message.content);
          body.replaceWith(field);
          edit.textContent = "Сохранить";
          editing = true;
          return;
        }
        call(function () {
          return fetch("/api/messages/" + encodeURIComponent(message.id), {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content: field.value })
          });
        }).then(function (data) {
          if (data === null) return;
          editing = false;
          load();
        });
      });

      var remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "Удалить";
      remove.addEventListener("click", function () {
        call(function () {
          return fetch("/api/messages/" + encodeURIComponent(message.id), {
            method: "DELETE"
          });
        }).then(function (data) {
          if (data === null) return;
          if (pending && String(pending.id) === String(message.id)) pending = null;
          editing = false;
          load();
        });
      });

      box.appendChild(who);
      box.appendChild(body);
      box.appendChild(edit);
      box.appendChild(remove);
      listEl.appendChild(box);
    });
  }

  function load() {
    return call(function () {
      return fetch("/api/messages", { method: "GET" });
    }).then(function (data) {
      if (data === null) return null;
      var list = rowsFrom(data);
      items = withPending(list);
      if (!editing) draw();
      return list;
    });
  }

  function waitFor(id) {
    var mine = ++token;
    var started = Date.now();
    thinkingEl.hidden = false;

    function stop() {
      if (mine !== token) return;
      thinkingEl.hidden = true;
      pending = null;
    }

    function step() {
      if (mine !== token) return;
      if (Date.now() - started >= 60000) {
        stop();
        return;
      }
      setTimeout(function () {
        if (mine !== token) return;
        load().then(function (list) {
          if (mine !== token) return;
          if (list && hasReply(list, id)) {
            stop();
            return;
          }
          step();
        });
      }, 1000);
    }

    step();
  }

  function send() {
    var content = inputEl.value.trim();
    if (!content) return;
    call(function () {
      return fetch("/api/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: content })
      });
    }).then(function (data) {
      if (!data || data.id == null) return;
      inputEl.value = "";
      pending = data;
      items = withPending(items);
      editing = false;
      draw();
      waitFor(data.id);
    });
  }

  inputEl.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  });

  document.getElementById("form").addEventListener("submit", function (event) {
    event.preventDefault();
    send();
  });

  fetch("/api/health")
    .then(function (response) {
      if (!response.ok) return null;
      return response.json();
    })
    .then(function (data) {
      if (data && data.model != null && data.model !== "") {
        modelEl.textContent = String(data.model);
      }
    })
    .catch(function () {});

  load();
})();

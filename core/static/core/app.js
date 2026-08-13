(() => {
  "use strict";

  const q = (selector, scope = document) => scope.querySelector(selector);
  const qa = (selector, scope = document) => [...scope.querySelectorAll(selector)];

  function csrfToken() {
    const cookie = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("csrftoken="));
    return cookie ? decodeURIComponent(cookie.split("=").slice(1).join("=")) : "";
  }

  function initialiseNavigation() {
    const toggle = q("[data-nav-toggle]");
    const nav = q("[data-primary-nav]");
    if (!toggle || !nav) return;

    toggle.addEventListener("click", () => {
      const open = nav.classList.toggle("is-open");
      toggle.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", String(open));
    });

    qa("a", nav).forEach((link) => link.addEventListener("click", () => {
      nav.classList.remove("is-open");
      toggle.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
    }));
  }

  function initialiseFlashes() {
    qa("[data-flash-dismiss]").forEach((button) => {
      button.addEventListener("click", () => button.closest("[data-flash]")?.remove());
    });
  }

  function initialiseModals() {
    const closeModal = (modal) => {
      if (!modal) return;
      modal.hidden = true;
      document.body.classList.remove("modal-open");
      const opener = document.querySelector(`[data-modal-open="${modal.id}"]`);
      opener?.focus();
    };

    qa("[data-modal-open]").forEach((opener) => {
      opener.addEventListener("click", () => {
        const modal = document.getElementById(opener.dataset.modalOpen);
        if (!modal) return;
        modal.hidden = false;
        document.body.classList.add("modal-open");
        window.setTimeout(() => q("input, button, [href]", modal)?.focus(), 0);
      });
    });

    qa("[data-modal]").forEach((modal) => {
      qa("[data-modal-close]", modal).forEach((closer) => closer.addEventListener("click", () => closeModal(modal)));
    });

    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      qa("[data-modal]").forEach((modal) => {
        if (!modal.hidden) closeModal(modal);
      });
    });
  }

  function initialiseCopyCode() {
    qa("[data-copy-code]").forEach((button) => {
      button.addEventListener("click", async () => {
        const code = button.dataset.code || button.textContent.trim();
        const hint = q("small", button);
        try {
          await navigator.clipboard.writeText(code);
        } catch (_) {
          const textarea = document.createElement("textarea");
          textarea.value = code;
          textarea.style.position = "fixed";
          textarea.style.opacity = "0";
          document.body.append(textarea);
          textarea.select();
          document.execCommand("copy");
          textarea.remove();
        }
        if (hint) {
          const original = hint.textContent;
          hint.textContent = "Copied to clipboard";
          window.setTimeout(() => { hint.textContent = original; }, 1800);
        }
      });
    });
  }

  function initialiseJoinForm() {
    const form = q("[data-ajax-join]");
    if (!form) return;
    const feedback = q("[data-join-feedback]", form);
    const submit = q("button[type=submit]", form);
    const codeInput = q("[name=join_code]", form);

    codeInput?.addEventListener("input", () => {
      codeInput.value = codeInput.value.toUpperCase().replace(/[^A-Z0-9]/g, "");
      if (feedback) feedback.textContent = "";
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (feedback) feedback.textContent = "";
      if (submit) {
        submit.disabled = true;
        submit.dataset.label = submit.textContent;
        submit.textContent = "Joining…";
      }

      try {
        const response = await fetch(form.action, {
          method: "POST",
          body: new FormData(form),
          credentials: "same-origin",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
            "X-CSRFToken": csrfToken(),
          },
        });
        const payload = await response.json();
        if (!response.ok || !payload.ok) throw new Error(payload.error || "We couldn’t join that room. Please try again.");
        window.location.assign(payload.redirect_url);
      } catch (error) {
        if (feedback) feedback.textContent = error.message || "Could not connect to the room.";
        if (submit) {
          submit.disabled = false;
          submit.textContent = submit.dataset.label || "Join room →";
        }
      }
    });
  }

  function initialiseActivityBuilder() {
    const builder = q("[data-block-builder]");
    const form = q("[data-activity-form]");
    if (!builder || !form) return;

    const canvas = q("[data-builder-canvas]", builder);
    const empty = q("[data-builder-empty]", builder);
    const jsonInput = q("#id_content_json, [data-content-json], [name=content_json]", builder);
    if (!canvas || !jsonInput) return;

    const displayNames = { intro: "Explain", question: "Quick check", image: "Visual", video: "Video", resource: "Resource" };
    const symbols = { intro: "✎", question: "?", image: "◒", video: "▶", resource: "↗" };

    function valueField(label, key, value = "", options = {}) {
      const wrapper = document.createElement("label");
      wrapper.className = "field";
      const labelNode = document.createElement("span");
      labelNode.textContent = label;
      const control = options.textarea ? document.createElement("textarea") : document.createElement("input");
      control.dataset.field = key;
      control.value = value || "";
      if (!options.textarea) control.type = options.type || "text";
      if (options.placeholder) control.placeholder = options.placeholder;
      if (options.required) control.required = true;
      wrapper.append(labelNode, control);
      return wrapper;
    }

    function choiceRow(value = "", index = 0) {
      const row = document.createElement("div");
      row.className = "choice-row";
      const letter = document.createElement("span");
      letter.textContent = String.fromCharCode(65 + index);
      const input = document.createElement("input");
      input.type = "text";
      input.value = value || "";
      input.placeholder = `Choice ${index + 1}`;
      input.dataset.choice = "";
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "choice-remove";
      remove.dataset.choiceRemove = "";
      remove.setAttribute("aria-label", "Remove choice");
      remove.textContent = "×";
      row.append(letter, input, remove);
      return row;
    }

    function updateChoiceLabels(block) {
      qa("[data-choice-list] .choice-row", block).forEach((row, index) => {
        const letter = q("span", row);
        if (letter) letter.textContent = String.fromCharCode(65 + index);
      });
      const answer = q("[data-answer-select]", block);
      if (!answer) return;
      const previous = answer.value;
      const choices = qa("[data-choice]", block);
      answer.replaceChildren();
      choices.forEach((choice, index) => {
        const option = document.createElement("option");
        option.value = String(index);
        option.textContent = `Correct answer: ${String.fromCharCode(65 + index)}`;
        answer.append(option);
      });
      answer.value = [...answer.options].some((option) => option.value === previous) ? previous : "0";
    }

    function createQuestionFields(block, data) {
      const questionFields = document.createElement("div");
      questionFields.className = "builder-question-fields";
      questionFields.append(valueField("Question", "prompt", data.prompt || data.question || "", { textarea: true, placeholder: "What do you want learners to think about?", required: true }));
      questionFields.append(valueField("Optional feedback or explanation", "explanation", data.explanation || data.body || "", { textarea: true, placeholder: "What should they learn from this?" }));

      const choices = document.createElement("div");
      choices.className = "field";
      const label = document.createElement("span");
      label.textContent = "Choices";
      const list = document.createElement("div");
      list.dataset.choiceList = "";
      const currentChoices = Array.isArray(data.options || data.choices) && (data.options || data.choices).length ? (data.options || data.choices) : ["", ""];
      currentChoices.forEach((choice, index) => list.append(choiceRow(choice, index)));
      const add = document.createElement("button");
      add.type = "button";
      add.className = "add-choice";
      add.dataset.addChoice = "";
      add.textContent = "+ Add another choice";
      choices.append(label, list, add);

      const answerField = document.createElement("label");
      answerField.className = "field";
      const answerLabel = document.createElement("span");
      answerLabel.textContent = "Answer key";
      const answer = document.createElement("select");
      answer.dataset.answerSelect = "";
      answer.dataset.field = "answer";
      answer.value = String(Number.isInteger(data.answer) ? data.answer : 0);
      answerField.append(answerLabel, answer);
      questionFields.append(choices, answerField);
      block.append(questionFields);
      updateChoiceLabels(block);
      answer.value = String(Number.isInteger(data.answer) ? data.answer : 0);
    }

    function createBlock(type, data = {}) {
      const normalizedType = type === "text" ? "intro" : (type || "intro");
      const block = document.createElement("section");
      block.className = "builder-block";
      block.dataset.builderBlock = "";
      block.dataset.type = normalizedType;

      const head = document.createElement("div");
      head.className = "builder-block-head";
      const handle = document.createElement("span");
      handle.className = "builder-drag";
      handle.setAttribute("aria-hidden", "true");
      handle.textContent = "•••";
      const typeLabel = document.createElement("span");
      typeLabel.className = "builder-block-type";
      typeLabel.textContent = `${symbols[normalizedType] || "✦"} ${displayNames[normalizedType] || "Block"}`;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "builder-remove";
      remove.dataset.builderRemove = "";
      remove.setAttribute("aria-label", "Remove this block");
      remove.textContent = "×";
      head.append(handle, typeLabel, remove);

      const body = document.createElement("div");
      body.className = "builder-block-body";
      if (normalizedType === "question") {
        body.append(valueField("Short label (optional)", "title", data.title || data.heading || "", { placeholder: "e.g. Pause and predict" }));
        const tip = document.createElement("p");
        tip.className = "builder-block-tip";
        tip.textContent = "Add at least two choices, then choose the correct answer.";
        body.append(tip);
      } else if (normalizedType === "image" || normalizedType === "video") {
        body.append(valueField("Heading", "title", data.title || data.heading || "", { placeholder: "Give learners a focus" }));
        body.append(valueField(normalizedType === "video" ? "Video URL" : "Image URL", "url", data.url || data.media_url || "", { type: "url", placeholder: "https://…" }));
        body.append(valueField("Caption", "caption", data.caption || data.body || "", { textarea: true, placeholder: "What should learners notice?" }));
        body.append(valueField("Alt text", "alt", data.alt || data.alt_text || "", { placeholder: "Describe the visual" }));
      } else {
        body.append(valueField("Heading", "title", data.title || data.heading || "", { placeholder: "Set up the next idea" }));
        body.append(valueField("Content", "body", data.body || data.text || "", { textarea: true, placeholder: "Write a clear, learner-friendly prompt" }));
      }
      block.append(head, body);
      if (normalizedType === "question") createQuestionFields(block, data);
      canvas.append(block);
      updateEmptyState();
      return block;
    }

    function updateEmptyState() {
      if (!empty) return;
      empty.hidden = qa("[data-builder-block]", canvas).length > 0;
    }

    function serialiseBlock(block) {
      const type = block.dataset.type || "intro";
      const value = (field) => q(`[data-field="${field}"]`, block)?.value.trim() || "";
      if (type === "question") {
        return {
          type: "question",
          title: value("title"),
          prompt: value("prompt"),
          explanation: value("explanation"),
          options: qa("[data-choice]", block).map((choice) => choice.value.trim()),
          answer: Number(q("[data-answer-select]", block)?.value || 0),
        };
      }
      if (type === "image" || type === "video") {
        return { type, title: value("title"), url: value("url"), caption: value("caption"), alt: value("alt") };
      }
      return { type: "intro", title: value("title"), body: value("body") };
    }

    function loadExistingBlocks() {
      try {
        const parsed = JSON.parse(jsonInput.value || "[]");
        if (Array.isArray(parsed)) parsed.forEach((block) => createBlock(block.type, block));
      } catch (_) {
        // The server will show a useful validation error if a malformed existing
        // payload reaches it; the editor starts clean rather than breaking.
      }
      updateEmptyState();
    }

    qa("[data-add-block]", builder).forEach((button) => {
      button.addEventListener("click", () => {
        const type = button.dataset.addBlock;
        const block = createBlock(type, type === "question" ? { options: ["", ""], answer: 0 } : {});
        q("input, textarea", block)?.focus();
      });
    });

    canvas.addEventListener("click", (event) => {
      const remove = event.target.closest("[data-builder-remove]");
      if (remove) {
        remove.closest("[data-builder-block]")?.remove();
        updateEmptyState();
        return;
      }
      const addChoice = event.target.closest("[data-add-choice]");
      if (addChoice) {
        const block = addChoice.closest("[data-builder-block]");
        q("[data-choice-list]", block)?.append(choiceRow("", qa("[data-choice]", block).length));
        updateChoiceLabels(block);
        return;
      }
      const removeChoice = event.target.closest("[data-choice-remove]");
      if (removeChoice) {
        const block = removeChoice.closest("[data-builder-block]");
        const rows = qa("[data-choice-list] .choice-row", block);
        if (rows.length > 2) removeChoice.closest(".choice-row")?.remove();
        updateChoiceLabels(block);
      }
    });

    canvas.addEventListener("input", (event) => {
      const block = event.target.closest("[data-builder-block]");
      if (block && event.target.matches("[data-choice]")) updateChoiceLabels(block);
    });

    form.addEventListener("submit", () => {
      jsonInput.value = JSON.stringify(qa("[data-builder-block]", canvas).map(serialiseBlock));
    });

    loadExistingBlocks();
  }

  function initialisePlayer() {
    const player = q("[data-activity-player]");
    const form = q("[data-quiz-form]", player || document);
    if (!player || !form) return;
    const cards = qa("[data-question-card]", form);
    const payload = q("[data-answer-payload]", form);
    const indicator = q("[data-player-progress]", form);
    const label = q("[data-player-progress-label]", form);
    const answers = {};

    cards.forEach((card, index) => {
      card.dataset.questionIndex = String(index);
      qa('input[type="radio"]', card).forEach((input) => {
        input.addEventListener("change", () => {
          answers[String(index)] = input.value;
          if (payload) payload.value = JSON.stringify(answers);
          updateProgress();
        });
      });
    });

    function updateProgress() {
      const complete = Object.keys(answers).length;
      const total = cards.length;
      const percent = total ? Math.round((complete / total) * 100) : 0;
      if (indicator) indicator.style.width = `${percent}%`;
      if (label) label.textContent = total ? `${complete} of ${total} checks answered` : "Read through the activity";
    }

    form.addEventListener("submit", () => {
      if (payload) payload.value = JSON.stringify(answers);
    });
    updateProgress();
  }

  initialiseNavigation();
  initialiseFlashes();
  initialiseModals();
  initialiseCopyCode();
  initialiseJoinForm();
  initialiseActivityBuilder();
  initialisePlayer();
})();

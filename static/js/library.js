// static/js/library.js
// Module: Smart Learning Hub / Library
// Admin 5 - Study Quest
//
// Chức năng:
//  - Tự submit form khi thay đổi dropdown bộ lọc.
//  - Trim khoảng trắng ô tìm kiếm trước khi submit.
//  - Không phụ thuộc thư viện ngoài.

(function () {
  "use strict";

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  ready(function () {
    var form = document.getElementById("library-filter-form");
    if (!form) {
      return;
    }

    var subjectSelect = form.querySelector("#subject");
    var categorySelect = form.querySelector("#category");
    var keywordInput = form.querySelector("#q");

    // Tự submit khi thay đổi bộ lọc
    [subjectSelect, categorySelect].forEach(function (el) {
      if (!el) return;
      el.addEventListener("change", function () {
        if (keywordInput) {
          keywordInput.value = (keywordInput.value || "").trim();
        }
        form.submit();
      });
    });

    // Trim từ khóa khi submit
    form.addEventListener("submit", function () {
      if (keywordInput) {
        keywordInput.value = (keywordInput.value || "").trim();
      }
    });

    // Cho phép nhấn Enter trong ô tìm kiếm để submit
    if (keywordInput) {
      keywordInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
          event.preventDefault();
          keywordInput.value = (keywordInput.value || "").trim();
          form.submit();
        }
      });
    }
  });
})();
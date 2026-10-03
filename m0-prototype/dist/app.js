const state = {
  scenario: "laba",
  page: "today",
  feeling: "正常",
  garlicIntolerance: false,
  pantry: new Set(["鸡蛋", "西红柿", "豆腐"]),
  matched: false,
  favorite: false,
};

const recipes = {
  laba: {
    title: "腊八粥",
    image: "./assets/laba-porridge.png",
    imageAlt: "一碗含杂粮、红豆和红枣的腊八粥",
    badge: "今日节日食谱",
    meta: "2 人份 · 约 50 分钟 · 电饭煲",
    reasons: ["腊八节", "冬季暖食", "杭州常见食材"],
    why: "今天是腊八节，优先展示符合节日饮食文化且通过个人安全筛查的食谱。",
    ingredients: [["糯米", "40 克"], ["小米", "30 克"], ["红豆", "20 克，提前浸泡"], ["花生", "15 克"], ["红枣", "4 枚，去核"], ["清水", "900 毫升"]],
    steps: ["将红豆浸泡 4 小时，其他谷物淘洗干净。", "把全部食材放入电饭煲，加入清水。", "选择煮粥程序，烹煮约 45 分钟。", "搅匀后静置 5 分钟，确认温度适宜再食用。"],
    safety: "含花生；对花生过敏者不可使用。材料替换须来自审核后的食谱版本。",
    source: "节庆食谱示例 · 原型内容，待专业审核与正式签署 · 版本 M0.1",
  },
  chill: {
    title: "山药小米粥",
    image: "./assets/yam-millet-porridge.png",
    imageAlt: "一碗家常山药小米粥",
    badge: "今日推荐",
    meta: "2 人份 · 约 30 分钟 · 汤锅",
    reasons: ["自述有点着凉", "偏冷天气", "清淡易吞咽"],
    why: "依据你选择的轻微体感和偏冷天气，优先展示温热、清淡的日常食谱，不代表诊断或治疗。",
    ingredients: [["小米", "60 克"], ["鲜山药", "120 克，去皮切块"], ["清水", "900 毫升"]],
    steps: ["戴手套将山药去皮，切成小块。", "小米淘洗后与清水一同入锅。", "煮开后转小火，加入山药。", "继续煮 20 分钟，中途搅拌防止粘底。", "确认山药软熟后关火，稍降温再食用。"],
    safety: "处理鲜山药可能引起皮肤瘙痒；如有明确食材过敏或医生饮食限制，请勿食用。",
    source: "家常粥品示例 · 原型内容，待专业审核与正式签署 · 版本 M0.1",
  },
  tomatoEgg: {
    title: "番茄炒蛋",
    image: null,
    badge: "食材完全匹配",
    meta: "2 人份 · 约 15 分钟 · 炒锅",
    reasons: ["已有鸡蛋", "已有西红柿", "15 分钟完成"],
    why: "关键食材已经具备，不需要额外购买。豆腐可留作另一道菜。",
    ingredients: [["鸡蛋", "3 个"], ["西红柿", "2 个，切块"], ["食用油", "10 毫升"], ["盐", "约 1 克"]],
    steps: ["鸡蛋打散，西红柿洗净切块。", "锅中放油，将鸡蛋炒至凝固后盛出。", "原锅放入西红柿，翻炒至出汁。", "倒回鸡蛋，加盐翻匀后关火。"],
    safety: "含鸡蛋；对鸡蛋过敏者不可食用。",
    source: "家常菜示例 · 原型内容，待专业审核与正式签署 · 版本 M0.1",
  },
  tofuSoup: {
    title: "番茄豆腐汤",
    image: null,
    badge: "食材完全匹配",
    meta: "2 人份 · 约 20 分钟 · 汤锅",
    reasons: ["已有西红柿", "已有豆腐", "20 分钟完成"],
    why: "主要食材已经具备，使用常见厨具即可完成。",
    ingredients: [["西红柿", "2 个，切块"], ["北豆腐", "200 克，切块"], ["清水", "500 毫升"], ["盐", "约 1 克"]],
    steps: ["西红柿与豆腐分别洗切备用。", "锅中放入西红柿，小火翻炒至出汁。", "加入清水煮开，再放入豆腐。", "小火煮 8 分钟，加盐后关火。"],
    safety: "含大豆；对大豆过敏者不可食用。",
    source: "家常汤品示例 · 原型内容，待专业审核与正式签署 · 版本 M0.1",
  },
};

const el = {
  content: document.querySelector("#appContent"),
  lunarDate: document.querySelector("#lunarDate"),
  weatherLine: document.querySelector("#weatherLine"),
  cityName: document.querySelector("#cityName"),
  sheet: document.querySelector("#recipeSheet"),
  sheetContent: document.querySelector("#sheetContent"),
  backdrop: document.querySelector("#sheetBackdrop"),
  toast: document.querySelector("#toast"),
};

function recipeCard(recipeKey) {
  const r = recipes[recipeKey];
  return `
    <article class="recommend-card">
      <div class="recipe-image">
        <img src="${r.image}" alt="${r.imageAlt}" />
        <span class="image-badge">${r.badge}</span>
      </div>
      <div class="recipe-body">
        <div class="recipe-title-row">
          <h2>${r.title}</h2>
          <button class="favorite-button ${state.favorite ? "is-active" : ""}" data-action="favorite" type="button" aria-label="${state.favorite ? "取消收藏" : "收藏食谱"}">${state.favorite ? "♥" : "♡"}</button>
        </div>
        <p class="recipe-meta">${r.meta}</p>
        <div class="reason-tags">${r.reasons.map((item) => `<span class="reason-tag">${item}</span>`).join("")}</div>
        <button class="primary-button" data-recipe="${recipeKey}" type="button">看食材和做法</button>
        <p class="why-copy"><strong>为什么推荐？</strong> ${r.why}</p>
      </div>
    </article>`;
}

function renderToday() {
  const isChill = state.scenario === "chill";
  const recipeKey = isChill ? "chill" : "laba";
  el.lunarDate.textContent = isChill ? "九月初八 · 周一" : "腊月初八 · 周三";
  el.weatherLine.textContent = isChill ? "18℃ 小雨 · 偏凉 · 白露后" : "4℃ 晴 · 偏冷 · 腊八节";
  el.cityName.textContent = "杭州";

  el.content.innerHTML = `
    ${!isChill ? `<div class="festival-banner"><strong>今日腊八</strong><span>腊八食俗寄托着迎新纳福的心意，饮食仍以个人安全限制为先。</span></div>` : ""}
    <section class="checkin-card">
      <div class="checkin-header">
        <p class="section-kicker">今天感觉怎么样？</p>
        <button class="text-link" data-action="safety" type="button">先看安全提示</button>
      </div>
      <div class="feeling-chips" aria-label="今日体感">
        ${["正常", "有点着凉", "胃口较差", "睡眠不足", "口干"].map((feeling) => `<button class="chip ${state.feeling === feeling ? "is-active" : ""}" data-feeling="${feeling}" type="button">${feeling}</button>`).join("")}
      </div>
    </section>
    ${recipeCard(recipeKey)}
    <section class="alternative-section">
      <h3 class="section-title">还可以做</h3>
      <div class="alternative-grid" id="alternativeGrid">
        ${alternativeCards()}
      </div>
      ${!isChill ? `<div class="intolerance-toggle"><span>原型验证：我对蒜不耐受</span><button class="switch ${state.garlicIntolerance ? "is-on" : ""}" data-action="garlic" type="button" role="switch" aria-checked="${state.garlicIntolerance}"></button></div>` : ""}
    </section>
    <div class="safety-strip">日常饮食建议，不替代诊疗。若有高热、胸痛、呼吸困难等情况，请停止个性化推荐并及时就医。</div>`;
}

function alternativeCards() {
  if (state.scenario === "chill") {
    return `<button class="alternative-card" data-recipe="tofuSoup" type="button"><strong>番茄豆腐汤</strong><span>清淡 · 约 20 分钟</span></button><button class="alternative-card" data-recipe="tomatoEgg" type="button"><strong>番茄炒蛋</strong><span>家常 · 约 15 分钟</span></button>`;
  }
  const first = state.garlicIntolerance
    ? `<button class="alternative-card" data-recipe="chill" type="button"><strong>山药小米粥</strong><span>已排除含蒜食谱</span></button>`
    : `<button class="alternative-card" data-action="garlic-info" type="button"><strong>腊八蒜</strong><span>节日食俗 · 含蒜</span></button>`;
  return `${first}<button class="alternative-card" data-recipe="tofuSoup" type="button"><strong>番茄豆腐汤</strong><span>家常 · 约 20 分钟</span></button>`;
}

function renderPantry() {
  el.lunarDate.textContent = "手头有什么，就做什么";
  el.weatherLine.textContent = "只匹配经过审核的食谱模板";
  el.content.innerHTML = `
    <section class="pantry-header">
      <h2>我的食材</h2>
      <p>选择 1—15 种食材，我们会先检查个人过敏和限制条件。</p>
    </section>
    <div class="search-box">
      <input id="ingredientInput" type="text" inputmode="text" placeholder="搜索食材，如西红柿" aria-label="搜索食材" />
      <button data-action="add-ingredient" type="button">添加</button>
    </div>
    <section class="ingredient-section">
      <h3>常用食材 <span class="selected-count">已选 ${state.pantry.size} 种</span></h3>
      <div class="ingredient-chips">
        ${["鸡蛋", "西红柿", "豆腐", "青菜", "大米", "香菇", "土豆", "牛肉"].map((item) => `<button class="ingredient-chip ${state.pantry.has(item) ? "is-selected" : ""}" data-ingredient="${item}" type="button">${item}</button>`).join("")}
      </div>
    </section>
    <div class="pantry-options">
      <div class="option-tile"><small>可接受时间</small><strong>30 分钟以内</strong></div>
      <div class="option-tile"><small>用餐人数</small><strong>2 人</strong></div>
      <div class="option-tile"><small>现有厨具</small><strong>炒锅 · 汤锅</strong></div>
      <div class="option-tile"><small>可再购买</small><strong>最多 2 种</strong></div>
    </div>
    <button class="primary-button" data-action="match" type="button">看看能做什么</button>
    <div class="match-results" id="matchResults">${state.matched ? matchResults() : ""}</div>
    <div class="safety-strip">命中过敏或明确禁忌的食谱会被完全排除，不只显示警告。</div>`;
}

function matchResults() {
  if (!(state.pantry.has("鸡蛋") && state.pantry.has("西红柿")) && !(state.pantry.has("豆腐") && state.pantry.has("西红柿"))) {
    return `<div class="prototype-warning">当前组合没有安全的完整匹配。可以补充食材，或允许购买 1—2 种非关键材料后再试。</div>`;
  }
  return `
    <h3 class="section-title">找到 2 道菜</h3>
    <article class="match-card" data-recipe="tomatoEgg"><div class="match-top"><strong>番茄炒蛋</strong><span class="match-score">完全匹配</span></div><p>已有：鸡蛋、西红柿、基础调味品</p></article>
    <article class="match-card" data-recipe="tofuSoup"><div class="match-top"><strong>番茄豆腐汤</strong><span class="match-score">完全匹配</span></div><p>已有：西红柿、豆腐、基础调味品</p></article>`;
}

function renderProfile() {
  el.lunarDate.textContent = "我的";
  el.weatherLine.textContent = "只保存提供服务所需的信息";
  el.content.innerHTML = `
    <section class="profile-page">
      <h2>个人情况</h2>
      <p>这里展示 M0 信息架构，不收集真实健康数据。</p>
      <div class="profile-grid">
        <article class="profile-card"><div class="profile-card-row"><div><strong>城市与地域</strong><p>杭州 · 可手动修改</p></div><span class="status-pill">已填写</span></div></article>
        <article class="profile-card"><div class="profile-card-row"><div><strong>过敏与饮食限制</strong><p>${state.garlicIntolerance ? "已记录：对蒜不耐受" : "暂未填写"}</p></div><span class="status-pill">安全必填</span></div></article>
        <article class="profile-card"><div class="profile-card-row"><div><strong>口味与忌口</strong><p>清淡 · 不吃过辣</p></div><span class="status-pill">可修改</span></div></article>
        <article class="profile-card"><div class="profile-card-row"><div><strong>体质参考</strong><p>未完成，不影响使用通用季节食谱</p></div><span class="status-pill">可跳过</span></div></article>
        <article class="profile-card"><div class="profile-card-row"><div><strong>收藏与最近浏览</strong><p>${state.favorite ? "已收藏 1 道食谱" : "暂无收藏"}</p></div><span class="status-pill">本地原型</span></div></article>
        <article class="profile-card"><div class="profile-card-row"><div><strong>隐私与数据</strong><p>定位授权、数据导出与删除流程待 M0 冻结</p></div><span class="status-pill">待确认</span></div></article>
      </div>
    </section>`;
}

function render() {
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("is-active", item.dataset.page === state.page));
  if (state.page === "today") renderToday();
  if (state.page === "pantry") renderPantry();
  if (state.page === "profile") renderProfile();
}

function openRecipe(key) {
  const r = recipes[key] || recipes.chill;
  el.sheetContent.innerHTML = `
    ${r.image ? `<img class="sheet-hero" src="${r.image}" alt="${r.imageAlt}" />` : ""}
    <div class="sheet-body">
      <h2 id="recipeTitle">${r.title}</h2>
      <p class="sheet-subtitle">${r.meta}</p>
      <div class="reason-tags">${r.reasons.map((item) => `<span class="reason-tag">${item}</span>`).join("")}</div>
      <section class="sheet-section"><h3>食材</h3><ul class="ingredient-list">${r.ingredients.map(([name, amount]) => `<li><span>${name}</span><span>${amount}</span></li>`).join("")}</ul></section>
      <section class="sheet-section"><h3>制作步骤</h3><ol class="step-list">${r.steps.map((step) => `<li>${step}</li>`).join("")}</ol></section>
      <section class="sheet-section"><h3>过敏与不适用情况</h3><div class="prototype-warning">${r.safety}</div></section>
      <section class="sheet-section"><h3>来源与审核</h3><div class="source-box">${r.source}<br />日常饮食建议，不替代诊疗。</div></section>
    </div>`;
  el.sheet.hidden = false;
  el.backdrop.hidden = false;
  document.body.style.overflow = "hidden";
  document.querySelector("#sheetClose").focus();
}

function closeRecipe() {
  el.sheet.hidden = true;
  el.backdrop.hidden = true;
  document.body.style.overflow = "";
}

let toastTimer;
function showToast(message) {
  clearTimeout(toastTimer);
  el.toast.textContent = message;
  el.toast.hidden = false;
  toastTimer = setTimeout(() => { el.toast.hidden = true; }, 2400);
}

document.addEventListener("click", (event) => {
  const scenario = event.target.closest("[data-scenario]");
  if (scenario) {
    state.scenario = scenario.dataset.scenario;
    state.page = state.scenario === "pantry" ? "pantry" : "today";
    state.feeling = state.scenario === "chill" ? "有点着凉" : "正常";
    state.matched = state.scenario === "pantry";
    document.querySelectorAll("[data-scenario]").forEach((item) => item.classList.toggle("is-active", item === scenario));
    render();
    return;
  }

  const nav = event.target.closest("[data-page]");
  if (nav) { state.page = nav.dataset.page; render(); return; }

  const feeling = event.target.closest("[data-feeling]");
  if (feeling) {
    state.feeling = feeling.dataset.feeling;
    if (state.feeling === "有点着凉") state.scenario = "chill";
    render();
    return;
  }

  const recipe = event.target.closest("[data-recipe]");
  if (recipe) { openRecipe(recipe.dataset.recipe); return; }

  const ingredient = event.target.closest("[data-ingredient]");
  if (ingredient) {
    const item = ingredient.dataset.ingredient;
    state.pantry.has(item) ? state.pantry.delete(item) : state.pantry.add(item);
    state.matched = false;
    render();
    return;
  }

  const action = event.target.closest("[data-action]")?.dataset.action;
  if (action === "favorite") { state.favorite = !state.favorite; render(); showToast(state.favorite ? "已收藏" : "已取消收藏"); }
  if (action === "garlic") { state.garlicIntolerance = !state.garlicIntolerance; render(); showToast(state.garlicIntolerance ? "已排除含蒜食谱" : "已恢复腊八蒜备选"); }
  if (action === "garlic-info") showToast("腊八蒜含蒜；记录不耐受后将完全排除");
  if (action === "safety") showToast("高热、胸痛、呼吸困难等情况将停止个性化推荐");
  if (action === "match") { state.matched = true; render(); document.querySelector("#matchResults")?.scrollIntoView({ behavior: "smooth" }); }
  if (action === "add-ingredient") {
    const input = document.querySelector("#ingredientInput");
    if (input?.value.trim()) { state.pantry.add(input.value.trim()); state.matched = false; render(); }
  }
});

document.querySelector("#sheetClose").addEventListener("click", closeRecipe);
el.backdrop.addEventListener("click", closeRecipe);
document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !el.sheet.hidden) closeRecipe(); });
document.querySelector("#cityButton").addEventListener("click", () => showToast("拒绝定位时，可在这里手动选择城市"));

render();

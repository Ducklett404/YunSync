import { expect, test } from '@playwright/test'
import demoContent from '../../src/data/m2-content.json'

// Set VITE_YUNSYNC_API_BASE_URL=http://127.0.0.1:5186/mock-api, build H5,
// and run node scripts/run-h5-tests.mjs cloud.spec.ts.
test.skip(process.env.VITE_YUNSYNC_API_BASE_URL !== 'http://127.0.0.1:5186/mock-api', 'Requires the mock API H5 build')

const demoRecipe = demoContent.recipes.find(recipe => recipe.id === 'demo-yam-millet')!
const cloudRecipe = { ...demoRecipe, id: 'board-only-recipe', version: 'board-v2', name: '板端家常粥' }

test('旧食材响应在条件改动后无法写回或结束新请求', async ({ page }) => {
  const replies: Array<() => Promise<void>> = []
  await page.route('**/mock-api/v1/recommendations/pantry', async route => {
    const recipe = replies.length === 0 ? demoRecipe : cloudRecipe
    let complete!: () => void
    const handled = new Promise<void>(resolve => { complete = resolve })
    replies.push(async () => {
      await route.fulfill({ json: {
        matches: [{ recipe, kind: 'complete', targetServings: 2, matchedIngredients: ['番茄'], missingIngredients: [], substitutionsUsed: [] }],
        filteredCount: 0, message: '测试匹配',
      } })
      complete()
    })
    await handled
  })

  await page.goto('/#/pages/pantry/index')
  await page.locator('.search-input input').fill('番茄,豆腐,食用油')
  await page.locator('.add-action').click()
  const matchButton = page.locator('.primary-button')
  await matchButton.click()
  await expect.poll(() => replies.length).toBe(1)
  await page.locator('.selected-chip').filter({ hasText: '豆腐' }).click()
  await expect(matchButton).toHaveText('开始匹配')
  await matchButton.click()
  await expect.poll(() => replies.length).toBe(2)
  const priorResponse = page.waitForResponse(response => response.url().endsWith('/mock-api/v1/recommendations/pantry'))
  await replies[0]()
  await priorResponse
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))
  await expect(matchButton).toHaveText('正在匹配')
  await expect(page.locator('.result-name')).toHaveCount(0)
  await replies[1]()
  await expect(page.locator('.result-name')).toHaveText(cloudRecipe.name)
  await expect(page.locator('.result-name')).not.toHaveText(demoRecipe.name)
})

test('今日推荐可以打开板端独有的食谱并记录正确版本', async ({ page }) => {
  await page.route('**/mock-api/v1/recommendations/today', route => route.fulfill({ json: {
    main: cloudRecipe, alternatives: [], degraded: [], reasons: [],
    weather: { available: false, text: '天气暂不可用' },
  } }))
  const requestVersions: Array<string | null> = []
  await page.route('**/mock-api/v1/recipes/board-only-recipe*', route => {
    requestVersions.push(new URL(route.request().url()).searchParams.get('version'))
    return route.fulfill({ json: { recipe: cloudRecipe } })
  })

  await page.goto('/#/pages/today/index')
  await expect(page.locator('.recipe-name')).toHaveText(cloudRecipe.name)
  await page.getByText('看食材和做法', { exact: true }).click()
  await expect(page.locator('.title')).toHaveText(cloudRecipe.name)
  expect(requestVersions).toEqual(['board-v2'])
  await expect(page.locator('.trace-line').last()).toContainText('board-v2')
  await page.locator('.favorite-button').click()
  await page.getByText('有帮助', { exact: true }).click()
  await expect(page.locator('.feedback-button.selected')).toHaveText('有帮助')
  await page.goto('/#/pages/profile/index')
  await page.locator('.saved-actions').getByText('查看', { exact: true }).first().click()
  await expect(page.locator('.title')).toHaveText(cloudRecipe.name)
  await expect(page.locator('.favorite-button')).toContainText('已收藏')
})

test('离线只回退到同版本副本，在线下架或改版时停止展示旧内容', async ({ page }) => {
  let status = 503
  await page.route('**/mock-api/v1/recipes/demo-yam-millet*', route => route.fulfill({ status }))
  const detail = '/#/pages/recipe/detail?id=demo-yam-millet'
  await page.goto(`${detail}&version=${demoRecipe.version}`)
  await expect(page.getByText(`当前显示本机副本 · ${demoRecipe.version}`, { exact: true })).toBeVisible()
  await page.goto(`${detail}&version=board-v2`)
  await page.reload()
  await expect(page.getByText(/本机副本与推荐版本不一致/)).toBeVisible()

  status = 409
  await page.reload()
  await expect(page.getByText(/食谱版本已更新/)).toBeVisible()
  status = 404
  await page.goto(`${detail}&version=${demoRecipe.version}`)
  await page.reload()
  await expect(page.getByText('这条食谱暂不可用', { exact: true })).toBeVisible()
  await expect(page.locator('.favorite-button')).toHaveCount(0)
})

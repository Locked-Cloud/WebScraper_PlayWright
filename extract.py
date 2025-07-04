from bs4 import BeautifulSoup

# Sample HTML content (you can replace this with your HTML)
html_code = '''
<section class="container homepage-section homepage-categories-section">
  <h2 class="header-extra mb-3">الأقسام</h2>

  <ul class="categories-list">
          <li>
        <a href="https://chefaa.com:443/eg-ar/now/category/medications">
          <img data-src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/Now_1739868905.png" class="category-image ls-is-cached lazyloaded" alt="الأدوية" width="96" height="96" src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/Now_1739868905.png">

          <h2 class="mb-0 mt-2 fs-14">الأدوية</h2>
        </a>
      </li>
          <li>
        <a href="https://chefaa.com:443/eg-ar/now/category/hair-care">
          <img data-src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/Frame-2534_1744632197.png" class="category-image ls-is-cached lazyloaded" alt="العناية بالشعر" width="96" height="96" src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/Frame-2534_1744632197.png">

          <h2 class="mb-0 mt-2 fs-14">العناية بالشعر</h2>
        </a>
      </li>
          <li>
        <a href="https://chefaa.com:443/eg-ar/now/category/skin-care">
          <img data-src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/Frame-2457-1_1679493245.png" class="category-image ls-is-cached lazyloaded" alt="العناية بالبشرة" width="96" height="96" src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/Frame-2457-1_1679493245.png">

          <h2 class="mb-0 mt-2 fs-14">العناية بالبشرة</h2>
        </a>
      </li>
          <li>
        <a href="https://chefaa.com:443/eg-ar/now/category/daily-essentials">
          <img data-src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/Daily-Essentials_1707299956.png" class="category-image ls-is-cached lazyloaded" alt="العناية اليومية" width="96" height="96" src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/Daily-Essentials_1707299956.png">

          <h2 class="mb-0 mt-2 fs-14">العناية اليومية</h2>
        </a>
      </li>
          <li>
        <a href="https://chefaa.com:443/eg-ar/now/category/mom-baby">
          <img data-src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/Frame-2533_1744632175.png" class="category-image ls-is-cached lazyloaded" alt="الأم والطفل" width="96" height="96" src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/Frame-2533_1744632175.png">

          <h2 class="mb-0 mt-2 fs-14">الأم والطفل</h2>
        </a>
      </li>
          <li>
        <a href="https://chefaa.com:443/eg-ar/now/category/makeup-accessories">
          <img data-src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/Frame-2457-4_1667482979.png" class="category-image ls-is-cached lazyloaded" alt="المكياج و الاكسسوارات" width="96" height="96" src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/Frame-2457-4_1667482979.png">

          <h2 class="mb-0 mt-2 fs-14">المكياج و الاكسسوارات</h2>
        </a>
      </li>
          <li>
        <a href="https://chefaa.com:443/eg-ar/now/category/health-care-devices">
          <img data-src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/Frame-2458-1_1667483491.png" class="category-image ls-is-cached lazyloaded" alt="المستلزمات الطبية" width="96" height="96" src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/Frame-2458-1_1667483491.png">

          <h2 class="mb-0 mt-2 fs-14">المستلزمات الطبية</h2>
        </a>
      </li>
          <li>
        <a href="https://chefaa.com:443/eg-ar/now/category/vitamins-supplements">
          <img data-src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/Frame-2536_1741085282.png" class="category-image ls-is-cached lazyloaded" alt="الفيتامينات والمكملات" width="96" height="96" src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/Frame-2536_1741085282.png">

          <h2 class="mb-0 mt-2 fs-14">الفيتامينات والمكملات</h2>
        </a>
      </li>
          <li>
        <a href="https://chefaa.com:443/eg-ar/now/category/sexual-welness">
          <img data-src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/00000_1727793378.png" class="category-image ls-is-cached lazyloaded" alt="الصحة الجنسية" width="96" height="96" src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/00000_1727793378.png">

          <h2 class="mb-0 mt-2 fs-14">الصحة الجنسية</h2>
        </a>
      </li>
          <li>
        <a href="https://chefaa.com:443/eg-ar/now/category/pet-supplies">
          <img data-src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/Frame-2527_1704372631.png" class="category-image ls-is-cached lazyloaded" alt="مستلزمات الحيوانات" width="96" height="96" src="https://cdn.chefaa.com/filters:format(webp)/public/uploads/categories/Frame-2527_1704372631.png">

          <h2 class="mb-0 mt-2 fs-14">مستلزمات الحيوانات</h2>
        </a>
      </li>
      </ul>
</section>
'''

# Parse the HTML
soup = BeautifulSoup(html_code, 'html.parser')

# Extract all href links
hrefs = [a['href'] for a in soup.find_all('a', href=True)]

# Print them
for href in hrefs:
    print(href)

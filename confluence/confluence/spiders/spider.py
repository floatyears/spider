# -*- coding: UTF-8 -*-

import scrapy
from scrapy import Request, FormRequest
from confluence.items import *
import time
import urllib.parse
import logging
import scrapy_splash
import base64

script = """
function main(splash)
  splash:add_cookie{"JSESSIONID", "46C83638D0C86B696B3063C55B37628C", "/wiki", domain='stl.woobest.com'}
  assert(splash:go{
    splash.args.url,
    --headers=splash.args.headers,
    --http_method=splash.args.http_method,
    --body=splash.args.body,
    })
  assert(splash:wait(0.5))

  local entries = splash:history()
  local last_response = entries[#entries].response
  return splash:html()
end
"""

script_img = """
function main(splash)
  splash:add_cookie{"JSESSIONID", "46C83638D0C86B696B3063C55B37628C", "/wiki", domain='stl.woobest.com'}
  assert(splash:go{
    splash.args.url,
    --headers=splash.args.headers,
    --http_method=splash.args.http_method,
    --body=splash.args.body,
    })
  assert(splash:wait(0.5))

  local entries = splash:history()
  local last_response = entries[#entries].response
  return { png = splash:png() }
end
"""

class confluenceSpider(scrapy.Spider):
  name = "confluence"
  allowed_domains = ["stl.woobest.com"]
  download_delay = 2
  start_urls = [
        'https://stl.woobest.com/wiki/pages/viewpage.action?pageId=69046880',
        # 'https://stl.woobest.com/wiki/pages/viewpage.action?pageId=69057617',
  ]
  base_url = 'https://stl.woobest.com'
  sub_url = '/wiki/plugins/pagetree/naturalchildren.action?decorator=none&excerpt=false&sort=position&reverse=false&disableLinks=false&expandCurrent=true&hasRoot=true&treeId=0&startDepth=0'
  cookies = {
    'JSESSIONID': '46C83638D0C86B696B3063C55B37628C',
    # 'seraph.confluence': '90081919%3Af97fbcc80bac99ec4034de9a6dfbdb930e9cdcf2',
    'doc-sidebar': '300px'
  }

  def start_requests(self):  
    for url in self.start_urls:          
      yield scrapy_splash.SplashRequest(url, self.sub_space, args={
            # optional; parameters passed to Splash HTTP API
            'wait': 0.5,
            'lua_source': script,

            # 'url' is prefilled from request url
            # 'http_method' is set to 'POST' for POST requests
            # 'body' is set to request body for POST requests
        },
        endpoint='execute', # optional; default is render.html
        splash_url='http://127.0.0.1:8050' ,     # optional; overrides SPLASH_URL
        slot_policy=scrapy_splash.SlotPolicy.PER_DOMAIN,  # optional
      )
      # yield Request(url, cookies=self.cookies, meta={
      #   'splash': {
      #       'args': {
      #           # set rendering arguments here
      #           'html': 1,
      #           'png': 1,
      #           'http_method': 'GET',

      #           # 'url' is prefilled from request url
      #           # 'http_method' is set to 'POST' for POST requests
      #           # 'body' is set to request body for POST requests
      #       },

      #       # optional parameters
      #       'endpoint': 'render.html',  # optional; default is render.json
      #       'splash_url': 'http://127.0.0.1:8050',      # optional; overrides SPLASH_URL
      #       'slot_policy': scrapy_splash.SlotPolicy.PER_DOMAIN,
      #       'splash_headers': {},       # optional; a dict with headers sent to Splash
      #       'dont_process_response': True, # optional, default is False
      #       'dont_send_headers': True,  # optional, default is False
      #       'magic_response': False,    # optional, default is True
      #   }
      # }) 
  def req_page(self, url, callback):
    a = 1
    b = 1
    return scrapy_splash.SplashRequest(url, callback, args={
            # optional; parameters passed to Splash HTTP API
            'wait': 0.5,
            'lua_source': script,

            # 'url' is prefilled from request url
            # 'http_method' is set to 'POST' for POST requests
            # 'body' is set to request body for POST requests
        },
        endpoint='execute', # optional; default is render.html
        splash_url='http://127.0.0.1:8050' ,     # optional; overrides SPLASH_URL
        slot_policy=scrapy_splash.SlotPolicy.PER_DOMAIN,  # optional
      )

  def parse_space(self, response):
    # 首页左侧列表
    spaceList = response.css('.space-name')
    for space in spaceList:
      url = self.base_url + space.css('::attr(href)')[0].extract()
      self.req_page(url, self.sub_space)

  # 拼接获取子菜单 ajax 请求
  def sub_space(self, response):
    parsed = urllib.parse.urlparse(response.url)
    pageId = urllib.parse.parse_qs(parsed.query)['pageId'][0]
    treePageId = pageId #urllib.parse.parse_qs(parsed.query)['pageId'][0]
    url = self.base_url + self.sub_url + '&pageId=' + pageId + '&treePageId=' + treePageId + '&_=' + str((int(round(time.time() * 1000))))
    yield self.req_page(url, self.sub_ajax_menu)

  def sub_ajax_menu(self, response):
    li_list = response.css('li')
    for li in li_list:
      href = li.css('div.plugin_pagetree_children_content span ::attr(href)')[0].extract()
      url = self.base_url + href
    
      logging.info('yield url: ' + url)
      yield self.req_page(url, self.parse_page)
      
      # 是否有子菜单
      if (len(li.css('.no-children.icon')) == 0):
        if ('pageId' in href):
          parsed = urllib.parse.urlparse(href)
          
          logging.info('parse sub menu, href: ' + href)

          pageId = urllib.parse.parse_qs(parsed.query)['pageId'][0]
          sub_url = self.base_url + self.sub_url + '&pageId=' + pageId + '&_=' + str((int(round(time.time() * 1000))))

          logging.info('yield url: ' + sub_url)
          yield self.req_page(sub_url, self.sub_ajax_menu)
        else:
          urlx = self.base_url + href
          yield self.req_page(urlx, self.sub_space)

      
  # 处理页面内容
  def parse_page(self, response):
    content_selector = content = response.css('div#content div.wiki-content')
    title = response.css('#title-text a::text')[0].extract()
    bread_crumbs = response.css('ol#breadcrumbs a::text').extract()
    content = content_selector[0].extract()

    path = ''
    for bread_crumb in bread_crumbs:
      path = path + bread_crumb + '/'

    # 图片信息
    content = content.replace('&amp;', '&')
    imgs = content_selector.css('img')
    i = 1
    for img in imgs:
      src = img.css('::attr(src)')[0].extract()
      img_name = title + str(i) + '.png'
      # content = content.decode('utf-8').replace(src.decode('utf-8'), img_name).encode('utf-8')
      content = content.replace(src, img_name)
      i += 1

      img_url = self.base_url + src
      yield scrapy_splash.SplashRequest(url=img_url, callback=self.parse_img, args={
        'wait': 0.1,
        'lua_source': script_img,
      }, meta={
        'img_name': img_name,
        'path': path
      },
      endpoint='execute', # optional; default is render.html
      splash_url='http://127.0.0.1:8050' ,     # optional; overrides SPLASH_URL
      slot_policy=scrapy_splash.SlotPolicy.PER_DOMAIN,  # optional
      )

    item = ConfluenceItem()
    item['name'] = title
    item['path'] = path
    item['content'] = content

    yield item

  def parse_img(self, response):
    item = ImgItem()
    item['name'] = response.meta['img_name']
    item['path'] = response.meta['path']
    item['content'] = response.data['png']

    yield item



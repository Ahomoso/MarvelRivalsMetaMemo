from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def create_driver():
    options = Options()
    options.debugger_address = "127.0.0.1:9222"

    driver = webdriver.Chrome(options=options)

    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[-1])

    return driver
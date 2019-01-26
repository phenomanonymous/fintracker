from selenium import webdriver
from selenium.common import exceptions
from selenium.webdriver.chrome.options import Options
from seleniumrequests import Chrome
from googleapi import get_mint_email_verification_code
import time
import urllib
import inspect
import os

def get_headless_web_driver():
    options = webdriver.ChromeOptions()
    options.set_headless(headless=True)
    driver = Chrome(chrome_options=options)

    return driver

def get_logged_in_driver(email, password):
    try:
        print("Creating headless webdriver")
        driver = get_headless_web_driver()

        mint_url = "https://www.mint.com"
        print("Navigating to %s" % mint_url)
        driver.get(mint_url)
        driver.implicitly_wait(20)  # seconds

        print("Mint: clicking Log In")
        driver.find_element_by_link_text("Log In").click()
        # driver.find_element_by_class_name("js-auth-slider-toggle--login.btn.btn-primary").click()
        # the below url is what clicking "Log In" should bring you to, but its extremely obnoxious
        # driver.get("https://accounts.intuit.com/index.html?offering_id=Intuit.ifs.mint&namespace_id=50000026&redirect_url=https%3A%2F%2Fmint.intuit.com%2Foverview.event%3Futm_medium%3Ddirect%26cta%3Dnav_login_dropdown%26adobe_mc%3DMCMID%253D77002298059235586230670777420121551141%257CMCORGID%253D969430F0543F253D0A4C98C6%252540AdobeOrg%257CTS%253D1547966883%26ivid%3D3fb14f1c-243e-488a-bfa7-d16933881ab3")

        print("Mint: sending user")
        driver.find_element_by_id("ius-userid").send_keys(email)
        print("Mint: sending pass")
        driver.find_element_by_id("ius-password").send_keys(password)
        print("Mint: submitting")
        driver.find_element_by_id("ius-sign-in-submit-btn").submit()

        return driver
    except exceptions.NoSuchElementException as e:
        print(e)
        print("Writing page source to html/exceptionpage.html")
        dir_path = os.path.dirname(inspect.stack()[-1][1]) # inspect.stack returns stack of calls, -1 is first aka original calling script. [1] is the filename
        filepath = os.path.join(dir_path, 'html/exceptionpage.html')
        with open(filepath, 'w') as htmlfile:
            htmlfile.write(driver.page_source.encode('utf-8'))
        print("Quitting bad webdriver")
        driver.quit()

        return None


def get_mint_page(email, password):
    driver = None
    while not driver:
        driver = get_logged_in_driver(email, password)

    # Wait until logged in, just in case we need to deal with MFA.
    email_sent = False
    while not driver.current_url.startswith('https://mint.intuit.com/overview.event'):
        if "Hmm. That didn't work." in driver.page_source:
            print("Mint: LOGIN FAILED")
        elif "Check your email" in driver.page_source and email_sent:
            print("Mint: MADE IT TO NEXT CHECKPOINT, WAITING 60 SECONDS FOR EMAIL")
            time.sleep(60)
            code = get_mint_email_verification_code()
            print("Mint: GOT VERIFICATION CODE... %s" % code)
            print("Mint: SENDING KEYS %s TO INPUT FIELD" % code)
            driver.find_element_by_id("ius-mfa-confirm-code").send_keys(code)
            print("Mint: CLICKING CONTINUE BUTTON")
            driver.find_element_by_id("ius-mfa-otp-submit-btn").submit()
        elif "Let's make sure it's you" in driver.page_source:
            print("Mint: CHALLENGE PRESENTED")
            driver.find_element_by_id("ius-mfa-option-email").click()
            print("Mint: CHOSE EMAIL OPTION")
            driver.find_element_by_id("ius-mfa-options-submit-btn").submit()
            print("Mint: SUBMITTED CONTINUE BUTTON")
            email_sent = True
        elif "Signing In ..." in driver.page_source:
            print("Signing In ...")
        else:
            print("Encountered unhandled login response, saving page to html/unhandledheadlesspage.html")
            dir_path = os.path.dirname(inspect.stack()[-1][1]) # inspect.stack returns stack of calls, -1 is first aka original calling script. [1] is the filename
            filepath = os.path.join(dir_path, 'html/unhandledheadlesspage.html')
            with open(filepath, 'w') as htmlfile:
                htmlfile.write(driver.page_source.encode('utf-8'))
        # url = urllib.unquote(driver.current_url) # for python2
        # print(url)
        # print(urllib.parse.unquote(driver.current_url)) # for python3
        time.sleep(1)

    # The normal flow can lead to a "It may have been moved or deleted" error in headless mode, so the following get() can be used as a workaround
    # Leaving it commented out until I run into the error again
    # driver.get("https://mint.intuit.com/overview.event?utm_medium=direct&cta=nav_login_dropdown")
    driver.implicitly_wait(60)  # wait up to 60s to find the transactions button.  The page can take a little while to load so I want to give it plenty
    print("Finding transactions...")
    driver.find_element_by_id("transaction")
    print("Found transactions")

    return driver

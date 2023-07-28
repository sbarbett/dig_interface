dig_interface
======================

This project originated from a request by my colleagues. We work for an authoritative DNS provider, and they had the idea to embed a dig-like interface within our ZenDesk help center. I have another similar applet that uses DoH to fetch DNS lookups, using JS, from a form in Guide. For this utility, however, I'm doing the UDP DNS querying "server-side" on a Lambda function with the 'dnspython' module. There's a bit of legwork involved in getting this to function properly. Anyone that's worked with Lambda is probably aware that most of the popular Python modules (like 'requests') aren't available "out-of-box" with their (somewhat barebones) Python 3 implementation. Also, ZenDesk, by default, doesn't allow you to embed scripts in your Guide. You have to enable a frighteningly-worded setting through Guide Admin.

## Zendesk Guide: Displaying "Unsafe Content"

Go to your Guide Admin. It should go without saying, but you must be a Zendesk Administrator to do this. From Guide Admin, click on the "cogwheel" in the far left navigation panel. Scroll down to "Security" and look for this setting.

```
[ ] Display unsafe content
Warning: Enabling this will allow potentially malicious code to be executed when viewing articles.
```

Check the box. This has to be enabled otherwise ZenDesk will erase any JS you attempt to embed in the source of your articles.

## Creating the Lambda Function and Enabling CORS

Create a Lambda function like so:

1. Select the radio button for "Author from scratch"
2. Give it whatever name you like
3. For "Runtime," choose Python 3.xx (whatever the "latest supported" is should be fine, though who knows how far into the future someone might be reading this)
4. Expand "Advanced Settings"
5. Check the box next to "Enable function URL"
6. Select "NONE" for "Auth type"
7. Check the box next to "Configure cross-origin resource sharing (CORS)"
8. Click "Create Function"

You can copy your function url from the function overview panel now. There's a couple more things that need to be done, configuration-wise.

1. Click on the "Configuration" tab on the panel where your code is displayed
2. Click on "Function URL" in the left navigation
3. Click on "Edit"
4. Make sure "Allow origin" is *
5. Under "Allow headers" add the following: "content-type", "access-control-allow-origin" and "access-control-allow-credentials"
6. Under "Allow methods" select "POST" or "*"

In order for our JS to fetch this function from the browser, we have to enable CORS and add the headers included by ZenDesk. This particular applet only uses POST, so that's the only HTTP method I've enabled.

## Deploying to Lambda

You need to install the 'dnspython' library to a local directory with pip using the -t switch.

```bash
mkdir lambda_package
cd lambda_package
pip install dnspython -t .
```

Put lambda_function.py in this directory then zip it up.

```bash
zip -r lambda_package.zip .
```

In the Management Console:

1. Pull up your Lambda function
2. Click "Upload from" then select ".zip file"
3. Upload "lambda_package.zip"

## Deploying to ZenDesk

Go to your Guide, add a new article, click the "`</>`" symbol on the rich text editor to open the "source code" then simply paste in the contents of interface.html. Replace the example url with your actual Lambda function url.

```javascript
const lambdaUrl = 'https://example.lambda-url.region.on.aws/'
```

## The Interface

I didn't attempt to fully replicate all the functionality of the command line dig tool. Dig has a lot of different switches and not all of them seem particularly useful. I may expand the options in future iterations of this code.

### Domains

This is the only truly "required" field. These are the domains/hostnames to be queried. They can be separated by line breaks, commas or semicolons. The code will attempt to validate that these are valid DNS.

### Record Type

All the different record types. Many of these are unnecessary. 

### Options

These are emulating some of the switches that dig has.

* Trace [`+trace`]: Traces the delegation path from the root servers. There wasn't a way for dnspython to do this natively, so I'm attempting to recreate the behavior by starting with a query against the root server, following it's answer to the TLD server, then the authoritative server, etc.
* Short [`+short`]: Dig gives verbose answers by default. 'Short' mode is exactly what is sounds like.
* No recursion [`+norec`]: Disables recursion, i.e. prevents the non-authoritative resolution of names.
* DNSSEC [`+dnssec`]: Requests DNSSEC records
* Checking disabled [`+cdflag`]: Requests DNSSEC validation not be performed
* Search all authoritative nameservers [`+nssearch`]: Attempts to find authoritative name servers and display the SOA record each NS has for the zone.

### Nameservers

These are the nameservers to query against. It will default to Vercara's public DNS servers, 64.6.64.6 and 64.6.65.6, but you can change that to whatever. I commonly tested against 8.8.8.8 and 8.8.4.4 (Google). The application will attempt to query all the domains from the "domains" input against each of the nameservers in the "nameservers" input.

### Base64 Encoded String

The purpose of this is for sharing queries. The base64 string is a representation of the current state of the form. If you copy this string, refresh the form and paste it into the base64 input field, it will repopulate the form automatically. It is just the minified json of the query information, encoded.

### Output

Output is displayed in both JSON and, for sentimental reasons, a traditional "dig-style" markup.

## License

This project is licensed under the terms of the MIT license. See LICENSE.md for more details.
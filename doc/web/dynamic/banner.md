
def banner(**kwargs):
    yield '''
<!-- ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ SEECR BANNER ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ -->
<div id="seecr-banner" class="vcard">
    <div class="wrap">
        <h2>By <span class="org">Seecr</span></h2>

        <p class="note">Software Craftsmanship</p>
        <p>
            <a class="url" href="http://seecr.nl" rel="me" title="Visit the Seecr website">Seecr - Software Craftsmanship</a>
            By <span class="fn">Erik J. Groeneveld</span>, <a href="mailto:erik@seecr.nl" class="email">erik@seecr.nl</a><br>
            This site was last updated on June 24<sup>th</sup> 2011</p>

    </div>
</div>
<!-- ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ SEECR BANNER ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ -->
'''

def main(**kwargs):
    yield http.redirect('/')

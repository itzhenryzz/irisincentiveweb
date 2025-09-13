// Import the functions you need from the libraries you installed with npm
import { Connection, PublicKey, Transaction } from '@solana/web3.js';
import { getAssociatedTokenAddress, createAssociatedTokenAccountInstruction } from '@solana/spl-token';

// --- Page Elements ---
const claimButton = document.getElementById('claimButton');
const walletAddressInput = document.getElementById('walletAddress');
const messageDiv = document.getElementById('message');

// --- State and Constants ---
let provider;
let wallet;
let adBlockerDetected = false;
const TOKEN_MINT_ADDRESS = '5FMU7DUgkD8cA8hBXc4QSsLA7PzJGSfYEtZBYA1hoCf2';

// --- Helper Functions ---
function showMessage(text, type) {
    messageDiv.textContent = text;
    messageDiv.className = type;
}

function checkAdBlocker() {
    const adUrl = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js';
    fetch(new Request(adUrl)).catch(() => {
        adBlockerDetected = true;
        claimButton.disabled = true;
        claimButton.textContent = 'Ad Blocker Detected';
        showMessage('Please disable ad blocker to support and use the faucet.', 'error');
    });
}
setTimeout(checkAdBlocker, 500);

// --- Main Application Logic ---
claimButton.addEventListener('click', async () => {
    // 1. Handle Wallet Connection
    if (!provider || !provider.isConnected) {
        if (!window.solana) {
            return showMessage('Solana wallet not found. Please install Phantom or Solflare.', 'error');
        }
        provider = window.solana;
        try {
            console.log("Connecting wallet...");
            await provider.connect();
            wallet = provider.publicKey.toString();
            walletAddressInput.value = wallet;
            walletAddressInput.disabled = true;
            claimButton.textContent = 'Claim Tokens!';
            return showMessage('Wallet connected! Click again to claim.', 'success');
        } catch (err) {
            console.error("Wallet connection failed:", err);
            return showMessage('Failed to connect wallet.', 'error');
        }
    }

    // 2. Handle Claiming Process
    const walletAddress = walletAddressInput.value;
    if (!walletAddress) {
        return showMessage('Please provide a wallet address!', 'error');
    }
    if (adBlockerDetected) {
        return showMessage('Please disable your ad blocker to use the faucet.', 'error');
    }

    claimButton.disabled = true;
    claimButton.textContent = 'Processing...';
    showMessage('Please wait, preparing transaction...', 'info');

    try {
        console.log("Setting up Solana connection and keys...");
        const connection = new Connection('https://snowy-sleek-moon.solana-mainnet.quiknode.pro/b782686111aa4eac5d9df855722fc24d95c7cc98/', 'confirmed');
        const recipientPublicKey = new PublicKey(walletAddress);
        const mintPublicKey = new PublicKey(TOKEN_MINT_ADDRESS);

        console.log("Finding Associated Token Account (ATA)...");
        const associatedTokenAddress = await getAssociatedTokenAddress(
            mintPublicKey,
            recipientPublicKey
        );
        console.log("ATA Address:", associatedTokenAddress.toBase58());

        console.log("Checking if ATA exists...");
        const accountInfo = await connection.getAccountInfo(associatedTokenAddress);

        if (!accountInfo) {
            console.log("ATA not found. Creating transaction...");
            showMessage('Token account not found. Please approve transaction to create it...', 'info');

            const transaction = new Transaction().add(
                createAssociatedTokenAccountInstruction(
                    recipientPublicKey, // Payer
                    associatedTokenAddress,
                    recipientPublicKey, // Owner
                    mintPublicKey
                )
            );

            const { blockhash } = await connection.getLatestBlockhash();
            transaction.recentBlockhash = blockhash;
            transaction.feePayer = recipientPublicKey;

            console.log("Requesting user to sign ATA creation transaction...");
            const signedTx = await provider.signTransaction(transaction);
            const txid = await connection.sendRawTransaction(signedTx.serialize());
            console.log("ATA creation transaction sent, confirming...", txid);
            await connection.confirmTransaction(txid);
            console.log("ATA creation confirmed.");
            showMessage('Account created! Claiming tokens...', 'info');
        } else {
            console.log("ATA already exists.");
        }

        // 3. Call Backend Server
        console.log("Calling backend server at /claim...");
        const response = await fetch('/claim', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ wallet_address: walletAddress }),
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Backend request failed.');
        }
        
        console.log("Backend response successful:", data);
        showMessage(data.message, 'success');
        const explorerLink = `https://explorer.solana.com/tx/${data.transaction_signature}`;
        messageDiv.innerHTML += ` <a href="${explorerLink}" target="_blank" style="color: var(--neon-end);">View Transaction</a>`;

    } catch (error) {
        console.error('A critical error occurred:', error);
        showMessage(error.message || 'An unknown error occurred. Check console.', 'error');
    } finally {
        claimButton.disabled = false;
        claimButton.textContent = 'Claim Tokens!';
    }
});